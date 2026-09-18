"""
效果参数优化训练器类
参考 Antares 哲学：精悍模型 + 强化学习 = 精准调参

构建10M参数级别的回归模型（多层感知机）
输入：风格标签 + 基础参数
输出：优化后的效果参数
"""
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from torch.optim.lr_scheduler import CosineAnnealingLR, CosineAnnealingWarmRestarts
from torch.utils.data import DataLoader, Dataset, TensorDataset

from core.torch_runtime import infer_ctx
from models.utils.metrics import cost_effectiveness_ratio, count_parameters

from .trainer_base import BaseTrainer, TrainingConfig, TrainingResult

logger = logging.getLogger(__name__)


class ParamOptimModel(nn.Module):
    """10M参数级别的多层感知机回归模型

    针对AE效果参数优化场景设计，包含：
    - 输入层：风格标签(one-hot) + 效果类型(one-hot) + 基础参数
    - 多个隐藏层，总参数量约10M
    - 输出层：优化后的效果参数
    """

    def __init__(self, input_dim: int, output_dim: int, hidden_dim: int = 2560, num_layers: int = 4):
        super().__init__()

        layers = []
        prev_dim = input_dim

        for i in range(num_layers):
            if i < num_layers - 1:
                current_dim = hidden_dim
            else:
                current_dim = hidden_dim // 2

            layers.append(nn.Linear(prev_dim, current_dim))
            layers.append(nn.GELU())
            layers.append(nn.LayerNorm(current_dim))
            layers.append(nn.Dropout(0.1))
            prev_dim = current_dim

        layers.append(nn.Linear(prev_dim, output_dim))
        layers.append(nn.Sigmoid())

        self.network = nn.Sequential(*layers)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.network(x)

    def count_params(self) -> float:
        total_params = sum(p.numel() for p in self.parameters())
        return total_params / 1_000_000


class ParamOptimDatasetTorch(Dataset):
    """PyTorch数据集包装器"""

    def __init__(self, data: list[dict]):
        self.data = data
        self.inputs = torch.stack([torch.from_numpy(s['input_vector']) for s in data])
        self.targets = torch.stack([torch.from_numpy(s['output_vector']) for s in data])

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.inputs[idx], self.targets[idx]


class ParamOptimTrainer(BaseTrainer):
    """效果参数优化训练器"""

    def __init__(self, config: TrainingConfig):
        super().__init__(config)
        self._model: ParamOptimModel | None = None
        self._criterion: nn.Module | None = None
        self._optimizer: optim.Optimizer | None = None
        self._scheduler: Any | None = None
        self._input_dim: int = 0
        self._output_dim: int = 0
        self._device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')

    def load_dataset(self, train_data: list[dict], eval_data: list[dict] = None) -> None:
        if train_data:
            self._input_dim = train_data[0]['input_vector'].shape[0]
            self._output_dim = train_data[0]['output_vector'].shape[0]

            self._train_dataset = ParamOptimDatasetTorch(train_data)
            logger.info(f"Loaded train dataset: {len(self._train_dataset)} samples")

        if eval_data:
            self._eval_dataset = ParamOptimDatasetTorch(eval_data)
            logger.info(f"Loaded eval dataset: {len(self._eval_dataset)} samples")

    def load_base_model(self) -> None:
        self._model = ParamOptimModel(
            input_dim=self._input_dim,
            output_dim=self._output_dim,
            hidden_dim=2560,
            num_layers=4,
        )
        self._model.to(self._device)

        params_million = self._model.count_params()
        logger.info(f"Model created with {params_million:.2f}M parameters")

        self._criterion = nn.MSELoss()
        self._optimizer = optim.AdamW(
            self._model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )

        if self.config.lr_scheduler_type == 'cosine_with_restarts':
            self._scheduler = CosineAnnealingWarmRestarts(
                self._optimizer,
                T_0=100,
                T_mult=2,
            )
        else:
            self._scheduler = CosineAnnealingLR(
                self._optimizer,
                T_max=1000,
            )

    def train(self) -> TrainingResult:
        if self._model is None or self._train_dataset is None:
            raise ValueError("Model and dataset must be loaded before training")

        self._start_training()

        train_loader = DataLoader(
            self._train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,
        )

        best_eval_loss = float('inf')
        epochs_without_improvement = 0
        total_steps = 0

        for epoch in range(self.config.epochs):
            self._epoch = epoch
            self._model.train()
            epoch_loss = 0.0
            num_batches = 0

            for batch_idx, (inputs, targets) in enumerate(train_loader):
                inputs = inputs.to(self._device)
                targets = targets.to(self._device)

                self._optimizer.zero_grad()

                outputs = self._model(inputs)
                loss = self._criterion(outputs, targets)

                loss.backward()

                torch.nn.utils.clip_grad_norm_(
                    self._model.parameters(),
                    self.config.max_grad_norm,
                )

                self._optimizer.step()
                self._scheduler.step()

                epoch_loss += loss.item()
                num_batches += 1
                total_steps += 1
                self._step = total_steps

                if total_steps % self.config.logging_steps == 0:
                    logger.info(
                        f"Epoch {epoch}, Step {total_steps}, "
                        f"Loss: {loss.item():.6f}"
                    )

                if total_steps % self.config.save_steps == 0:
                    self._save_checkpoint(total_steps)

            avg_train_loss = epoch_loss / num_batches
            logger.info(f"Epoch {epoch} completed, Avg Train Loss: {avg_train_loss:.6f}")

            if self._eval_dataset and total_steps % self.config.eval_steps == 0:
                eval_metrics = self.evaluate()
                eval_loss = eval_metrics.get('mse', float('inf'))

                if eval_loss < best_eval_loss:
                    best_eval_loss = eval_loss
                    epochs_without_improvement = 0
                    self._save_checkpoint(total_steps, is_best=True)
                else:
                    epochs_without_improvement += 1

                if epochs_without_improvement >= self.config.early_stopping_patience:
                    logger.info(f"Early stopping after {self.config.early_stopping_patience} epochs")
                    break

        self._end_training()

        final_eval_metrics = self.evaluate()
        training_time = time.time() - self._start_time

        model_path = self._save_checkpoint(total_steps, is_best=True)
        params_million = self._model.count_params()

        return TrainingResult(
            model_path=model_path,
            total_steps=total_steps,
            total_epochs=self._epoch + 1,
            train_loss=avg_train_loss,
            eval_loss=final_eval_metrics.get('mse', 0.0),
            eval_metrics=final_eval_metrics,
            params_million=params_million,
            training_time_seconds=training_time,
            cost_estimate_usd=self._estimate_cost(params_million, training_time),
        )

    def evaluate(self) -> dict[str, float]:
        if self._model is None or self._eval_dataset is None:
            return {}

        self._model.eval()

        eval_loader = DataLoader(
            self._eval_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=0,
        )

        all_targets = []
        all_predictions = []

        with infer_ctx(self._device):
            for inputs, targets in eval_loader:
                inputs = inputs.to(self._device)
                targets = targets.to(self._device)

                outputs = self._model(inputs)

                all_targets.extend(targets.cpu().numpy())
                all_predictions.extend(outputs.cpu().numpy())

        all_targets = np.array(all_targets)
        all_predictions = np.array(all_predictions)

        mse = mean_squared_error(all_targets, all_predictions)
        mae = mean_absolute_error(all_targets, all_predictions)
        r2 = r2_score(all_targets, all_predictions)

        metrics = {
            'mse': mse,
            'mae': mae,
            'r2': r2,
            'rmse': np.sqrt(mse),
        }

        logger.info(f"Evaluation Results - MSE: {mse:.6f}, MAE: {mae:.6f}, R2: {r2:.4f}")

        return metrics

    def save_model(self, output_path: str) -> str:
        if self._model is None:
            raise ValueError("No model to save")

        os.makedirs(output_path, exist_ok=True)

        model_path = os.path.join(output_path, 'model.pt')
        torch.save({
            'model_state_dict': self._model.state_dict(),
            'input_dim': self._input_dim,
            'output_dim': self._output_dim,
        }, model_path)

        config_path = os.path.join(output_path, 'config.json')
        config_dict = {
            'model_name': self.config.model_name,
            'input_dim': self._input_dim,
            'output_dim': self._output_dim,
            'hidden_dim': 2560,
            'num_layers': 4,
            'params_million': self._model.count_params(),
        }
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_dict, f, indent=2)

        logger.info(f"Model saved to {model_path}")
        return output_path

    def _save_checkpoint(self, step: int, is_best: bool = False):
        checkpoint_dir = os.path.join(self.config.output_dir, 'checkpoints')
        os.makedirs(checkpoint_dir, exist_ok=True)

        checkpoint_path = os.path.join(checkpoint_dir, f'model_step_{step}.pt')
        torch.save({
            'step': step,
            'epoch': self._epoch,
            'model_state_dict': self._model.state_dict(),
            'optimizer_state_dict': self._optimizer.state_dict(),
            'scheduler_state_dict': self._scheduler.state_dict(),
        }, checkpoint_path)

        if is_best:
            best_path = os.path.join(self.config.output_dir, 'best_model.pt')
            torch.save({
                'model_state_dict': self._model.state_dict(),
                'input_dim': self._input_dim,
                'output_dim': self._output_dim,
            }, best_path)
            return best_path

        return checkpoint_path

    def predict(self, input_vector: np.ndarray) -> np.ndarray:
        if self._model is None:
            raise ValueError("Model not loaded")

        self._model.eval()

        tensor_input = torch.from_numpy(input_vector).float().to(self._device)
        if len(tensor_input.shape) == 1:
            tensor_input = tensor_input.unsqueeze(0)

        with infer_ctx(self._device):
            output = self._model(tensor_input)

        return output.cpu().numpy().squeeze()

    @classmethod
    def load_model(cls, model_path: str, config: TrainingConfig) -> 'ParamOptimTrainer':
        trainer = cls(config)

        checkpoint = torch.load(model_path, map_location=trainer._device)
        input_dim = checkpoint.get('input_dim', 100)
        output_dim = checkpoint.get('output_dim', 16)

        trainer._model = ParamOptimModel(
            input_dim=input_dim,
            output_dim=output_dim,
            hidden_dim=2560,
            num_layers=4,
        )
        trainer._model.load_state_dict(checkpoint['model_state_dict'])
        trainer._model.to(trainer._device)
        trainer._model.eval()

        trainer._input_dim = input_dim
        trainer._output_dim = output_dim

        logger.info(f"Model loaded from {model_path}")
        return trainer
