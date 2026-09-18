"""
训练回调工具集
提供日志记录、早停、检查点、指标收集等训练回调。
"""
import json
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TrainingCallback(ABC):
    """训练回调基类
    
    所有训练回调都继承此类，实现相应的事件处理方法。
    """
    
    def __init__(self):
        self.trainer = None
    
    def on_init_end(self, trainer: Any) -> None:
        """训练器初始化结束时调用
        
        Args:
            trainer: 训练器实例
        """
        self.trainer = trainer
    
    def on_training_start(self, step: int, epoch: int, **kwargs) -> None:
        """训练开始时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
        """
        pass
    
    def on_training_end(self, step: int, epoch: int, **kwargs) -> None:
        """训练结束时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
        """
        pass
    
    def on_epoch_start(self, step: int, epoch: int, **kwargs) -> None:
        """每轮开始时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
        """
        pass
    
    def on_epoch_end(self, step: int, epoch: int, **kwargs) -> None:
        """每轮结束时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
        """
        pass
    
    def on_step_start(self, step: int, epoch: int, **kwargs) -> None:
        """每步开始时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
        """
        pass
    
    def on_step_end(self, step: int, epoch: int, **kwargs) -> None:
        """每步结束时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
        """
        pass
    
    def on_log(self, step: int, epoch: int, logs: dict[str, float], **kwargs) -> None:
        """记录日志时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
            logs: 日志数据
        """
        pass
    
    def on_evaluate(self, step: int, epoch: int, metrics: dict[str, float], **kwargs) -> None:
        """评估结束时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
            metrics: 评估指标
        """
        pass
    
    def on_save(self, step: int, epoch: int, output_path: str, **kwargs) -> None:
        """保存模型时调用
        
        Args:
            step: 当前步数
            epoch: 当前轮数
            output_path: 保存路径
        """
        pass


class LoggingCallback(TrainingCallback):
    """日志记录回调
    
    记录训练过程中的损失、学习率等指标。
    """
    
    def __init__(
        self,
        log_dir: str = "./logs",
        log_file: str = "training.log",
        log_every_steps: int = 10,
    ):
        """初始化日志回调
        
        Args:
            log_dir: 日志目录
            log_file: 日志文件名
            log_every_steps: 每隔多少步记录一次
        """
        super().__init__()
        self.log_dir = log_dir
        self.log_file = log_file
        self.log_every_steps = log_every_steps
        self._log_history: list[dict] = []
        self._start_time = 0.0
    
    def on_training_start(self, step: int, epoch: int, **kwargs) -> None:
        """训练开始"""
        self._start_time = time.time()
        os.makedirs(self.log_dir, exist_ok=True)
        logger.info(f"Training started, logs will be saved to {self.log_dir}")
    
    def on_step_end(self, step: int, epoch: int, **kwargs) -> None:
        """每步结束时记录日志"""
        if step % self.log_every_steps != 0:
            return
        
        loss = kwargs.get("loss", 0.0)
        lr = kwargs.get("learning_rate", 0.0)
        
        elapsed = time.time() - self._start_time
        steps_per_sec = step / elapsed if elapsed > 0 else 0
        
        log_entry = {
            "step": step,
            "epoch": epoch,
            "loss": loss,
            "learning_rate": lr,
            "elapsed_seconds": elapsed,
            "steps_per_second": steps_per_sec,
        }
        
        self._log_history.append(log_entry)
        
        logger.info(
            f"Step {step} | Epoch {epoch} | Loss: {loss:.4f} | "
            f"LR: {lr:.2e} | Speed: {steps_per_sec:.2f} steps/s"
        )
    
    def on_evaluate(self, step: int, epoch: int, metrics: dict[str, float], **kwargs) -> None:
        """评估结束时记录"""
        metrics_str = " | ".join(f"{k}: {v:.4f}" for k, v in metrics.items())
        logger.info(f"Eval at step {step} | {metrics_str}")
        
        log_entry = {
            "step": step,
            "epoch": epoch,
            "eval_metrics": metrics,
        }
        self._log_history.append(log_entry)
    
    def on_training_end(self, step: int, epoch: int, **kwargs) -> None:
        """训练结束时保存日志"""
        log_path = os.path.join(self.log_dir, self.log_file)
        with open(log_path, "w", encoding="utf-8") as f:
            json.dump(self._log_history, f, ensure_ascii=False, indent=2)
        
        elapsed = time.time() - self._start_time
        logger.info(f"Training completed in {elapsed:.2f}s, logs saved to {log_path}")
    
    @property
    def log_history(self) -> list[dict]:
        """获取历史日志"""
        return self._log_history


class EarlyStoppingCallback(TrainingCallback):
    """早停回调
    
    当监控指标在指定 patience 内没有改善时，停止训练。
    """
    
    def __init__(
        self,
        monitor: str = "eval_loss",
        patience: int = 3,
        min_delta: float = 0.0,
        mode: str = "min",
        verbose: bool = True,
    ):
        """初始化早停回调
        
        Args:
            monitor: 监控的指标名称
            patience: 容忍多少步没有改善
            min_delta: 最小改善幅度
            mode: min（越小越好）或 max（越大越好）
            verbose: 是否输出详细信息
        """
        super().__init__()
        self.monitor = monitor
        self.patience = patience
        self.min_delta = min_delta
        self.mode = mode
        self.verbose = verbose
        
        self.best_value = float("inf") if mode == "min" else float("-inf")
        self.best_step = 0
        self.wait = 0
        self.should_stop = False
    
    def _is_better(self, value: float) -> bool:
        """判断新值是否比最佳值好"""
        if self.mode == "min":
            return value < self.best_value - self.min_delta
        else:
            return value > self.best_value + self.min_delta
    
    def on_evaluate(self, step: int, epoch: int, metrics: dict[str, float], **kwargs) -> None:
        """评估后检查是否需要早停"""
        if self.monitor not in metrics:
            logger.warning(f"Monitor metric '{self.monitor}' not found in metrics")
            return
        
        current_value = metrics[self.monitor]
        
        if self._is_better(current_value):
            self.best_value = current_value
            self.best_step = step
            self.wait = 0
            if self.verbose:
                logger.info(f"New best {self.monitor}: {current_value:.4f} at step {step}")
        else:
            self.wait += 1
            if self.verbose:
                logger.info(
                    f"No improvement in {self.monitor} for {self.wait}/{self.patience} steps "
                    f"(best: {self.best_value:.4f} at step {self.best_step})"
                )
            
            if self.wait >= self.patience:
                self.should_stop = True
                if self.verbose:
                    logger.info(
                        f"Early stopping triggered at step {step}. "
                        f"Best {self.monitor}: {self.best_value:.4f} at step {self.best_step}"
                    )


class CheckpointCallback(TrainingCallback):
    """检查点保存回调
    
    定期保存模型检查点。
    """
    
    def __init__(
        self,
        output_dir: str = "./checkpoints",
        save_every_steps: int = 100,
        save_total_limit: int = 5,
        save_best_only: bool = False,
        monitor: str = "eval_loss",
        mode: str = "min",
    ):
        """初始化检查点回调
        
        Args:
            output_dir: 检查点保存目录
            save_every_steps: 每隔多少步保存一次
            save_total_limit: 最多保存多少个检查点
            save_best_only: 是否只保存最佳模型
            monitor: 监控指标（save_best_only=True 时使用）
            mode: min 或 max
        """
        super().__init__()
        self.output_dir = output_dir
        self.save_every_steps = save_every_steps
        self.save_total_limit = save_total_limit
        self.save_best_only = save_best_only
        self.monitor = monitor
        self.mode = mode
        
        self.best_value = float("inf") if mode == "min" else float("-inf")
        self._checkpoints: list[str] = []
        self.best_checkpoint_path = ""
    
    def _is_better(self, value: float) -> bool:
        """判断新值是否更好"""
        if self.mode == "min":
            return value < self.best_value
        else:
            return value > self.best_value
    
    def on_training_start(self, step: int, epoch: int, **kwargs) -> None:
        """训练开始时创建目录"""
        os.makedirs(self.output_dir, exist_ok=True)
    
    def on_step_end(self, step: int, epoch: int, **kwargs) -> None:
        """每步结束时检查是否需要保存"""
        if self.save_best_only:
            return
        
        if step % self.save_every_steps == 0 and step > 0:
            self._save_checkpoint(step, epoch, "checkpoint")
    
    def on_evaluate(self, step: int, epoch: int, metrics: dict[str, float], **kwargs) -> None:
        """评估后保存最佳模型"""
        if not self.save_best_only:
            return
        
        if self.monitor not in metrics:
            return
        
        current_value = metrics[self.monitor]
        
        if self._is_better(current_value):
            self.best_value = current_value
            self._save_checkpoint(step, epoch, "best")
    
    def _save_checkpoint(self, step: int, epoch: int, prefix: str) -> None:
        """保存检查点
        
        Args:
            step: 当前步数
            epoch: 当前轮数
            prefix: 文件名前缀
        """
        checkpoint_name = f"{prefix}_step_{step}_epoch_{epoch}"
        checkpoint_path = os.path.join(self.output_dir, checkpoint_name)
        
        if self.trainer is not None:
            try:
                self.trainer.save_model(checkpoint_path)
                self._checkpoints.append(checkpoint_path)
                logger.info(f"Checkpoint saved: {checkpoint_path}")
                
                self._prune_checkpoints()
            except Exception as e:
                logger.error(f"Failed to save checkpoint: {e}")
    
    def _prune_checkpoints(self) -> None:
        """删除旧的检查点，保持总数在限制内"""
        if self.save_total_limit is None or self.save_total_limit <= 0:
            return
        
        while len(self._checkpoints) > self.save_total_limit:
            oldest = self._checkpoints.pop(0)
            try:
                import shutil
                if os.path.exists(oldest):
                    shutil.rmtree(oldest, ignore_errors=True)
                    logger.info(f"Pruned old checkpoint: {oldest}")
            except Exception as e:
                logger.warning(f"Failed to prune checkpoint {oldest}: {e}")


class MetricsCallback(TrainingCallback):
    """指标收集回调
    
    收集训练过程中的所有指标，用于后续分析。
    """
    
    def __init__(self):
        """初始化指标回调"""
        super().__init__()
        self._train_metrics: list[dict] = []
        self._eval_metrics: list[dict] = []
        self._train_start_time = 0.0
        self._epoch_start_time = 0.0
    
    @property
    def train_metrics(self) -> list[dict]:
        """训练指标历史"""
        return self._train_metrics
    
    @property
    def eval_metrics(self) -> list[dict]:
        """评估指标历史"""
        return self._eval_metrics
    
    def on_training_start(self, step: int, epoch: int, **kwargs) -> None:
        """训练开始"""
        self._train_start_time = time.time()
    
    def on_epoch_start(self, step: int, epoch: int, **kwargs) -> None:
        """每轮开始"""
        self._epoch_start_time = time.time()
    
    def on_epoch_end(self, step: int, epoch: int, **kwargs) -> None:
        """每轮结束"""
        epoch_time = time.time() - self._epoch_start_time
        logger.info(f"Epoch {epoch} completed in {epoch_time:.2f}s")
    
    def on_step_end(self, step: int, epoch: int, **kwargs) -> None:
        """每步结束记录训练指标"""
        metrics = {
            "step": step,
            "epoch": epoch,
            "loss": kwargs.get("loss", 0.0),
            "learning_rate": kwargs.get("learning_rate", 0.0),
            "grad_norm": kwargs.get("grad_norm", 0.0),
        }
        self._train_metrics.append(metrics)
    
    def on_evaluate(self, step: int, epoch: int, metrics: dict[str, float], **kwargs) -> None:
        """评估结束记录评估指标"""
        eval_entry = {
            "step": step,
            "epoch": epoch,
            **metrics,
        }
        self._eval_metrics.append(eval_entry)
    
    def get_summary(self) -> dict[str, Any]:
        """获取训练总结
        
        Returns:
            Dict[str, Any]: 训练总结
        """
        total_time = time.time() - self._train_start_time if self._train_start_time > 0 else 0
        
        best_eval = {}
        if self._eval_metrics:
            best_eval = self._eval_metrics[-1]
        
        return {
            "total_training_time_seconds": total_time,
            "total_steps": len(self._train_metrics),
            "total_evals": len(self._eval_metrics),
            "final_train_loss": self._train_metrics[-1]["loss"] if self._train_metrics else 0.0,
            "best_eval_metrics": best_eval,
        }
