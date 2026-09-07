"""
JSX代码生成模型训练主脚本
整合数据准备、训练、评估、注册全流程
参考 Antares 哲学：精悍够用，垂直精调

运行方式：
    python models/train_jsx_code.py
"""
import os
import sys
import json
import logging
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def prepare_dataset():
    """准备训练数据集"""
    logger.info("=== Step 1: Preparing JSX dataset ===")
    
    from models.data.prepare_jsx_data import JSXDataCollector
    
    collector = JSXDataCollector()
    collector.build_dataset()
    
    synthetic = collector.generate_synthetic_samples(100)
    collector.dataset.extend(synthetic)
    
    dataset_path = collector.save_dataset()
    collector.save_stats()
    
    logger.info(f"Dataset prepared: {len(collector.dataset)} samples")
    logger.info(f"Dataset saved to: {dataset_path}")
    
    return dataset_path, len(collector.dataset)


def split_dataset(dataset_path: str, train_ratio: float = 0.8, val_ratio: float = 0.1):
    """划分训练/验证/测试集"""
    logger.info("=== Step 2: Splitting dataset ===")
    
    import random
    
    with open(dataset_path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    random.seed(42)
    random.shuffle(lines)
    
    n = len(lines)
    train_size = int(n * train_ratio)
    val_size = int(n * val_ratio)
    
    train_lines = lines[:train_size]
    val_lines = lines[train_size:train_size + val_size]
    test_lines = lines[train_size + val_size:]
    
    data_dir = Path(dataset_path).parent
    
    train_path = str(data_dir / "jsx_train.jsonl")
    val_path = str(data_dir / "jsx_val.jsonl")
    test_path = str(data_dir / "jsx_test.jsonl")
    
    with open(train_path, "w", encoding="utf-8") as f:
        f.writelines(train_lines)
    with open(val_path, "w", encoding="utf-8") as f:
        f.writelines(val_lines)
    with open(test_path, "w", encoding="utf-8") as f:
        f.writelines(test_lines)
    
    logger.info(f"Split: train={len(train_lines)}, val={len(val_lines)}, test={len(test_lines)}")
    
    return train_path, val_path, test_path


def train_model(train_path: str, val_path: str):
    """训练模型"""
    logger.info("=== Step 3: Training JSX code generation model ===")
    
    from models.training.jsx_code_trainer import JSXCodeTrainingConfig, JSXCodeTrainer
    
    config = JSXCodeTrainingConfig(
        model_name="jsx-code-generator",
        base_model_path="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        output_dir="./output/models",
        epochs=4,
        batch_size=1,
        learning_rate=2e-4,
        max_seq_length=512,
        gradient_accumulation_steps=8,
        lora_rank=16,
        lora_alpha=32,
        warmup_steps=20,
        logging_steps=5,
        save_steps=20,
        eval_steps=20,
    )
    
    trainer = JSXCodeTrainer(config)
    
    logger.info("Loading dataset...")
    trainer.load_dataset(train_path, val_path)
    
    logger.info("Loading base model...")
    trainer.load_base_model()
    
    logger.info("Starting training...")
    result = trainer.train()
    
    logger.info(f"Training complete!")
    logger.info(f"  - Model path: {result.model_path}")
    logger.info(f"  - Train loss: {result.train_loss:.4f}")
    logger.info(f"  - Eval loss: {result.eval_loss:.4f}")
    logger.info(f"  - Params: {result.params_million:.2f}M")
    logger.info(f"  - Time: {result.training_time_seconds:.2f}s")
    logger.info(f"  - Cost: ${result.cost_estimate_usd:.4f}")
    
    return trainer, result


def evaluate_model(trainer, test_path: str):
    """评估模型"""
    logger.info("=== Step 4: Evaluating model ===")
    
    from models.evaluation.jsx_code_evaluator import JSXCodeEvaluator
    from models.evaluation.evaluator_base import EvaluationConfig
    
    eval_config = EvaluationConfig(
        eval_name="jsx_code_eval",
        metric_names=["syntax_accuracy", "functional_accuracy", "code_bleu", "bleu"],
    )
    
    evaluator = JSXCodeEvaluator(eval_config)
    
    with open(test_path, "r", encoding="utf-8") as f:
        test_data = [json.loads(line) for line in f]
    
    evaluator.load_dataset(test_data)
    evaluator.load_model(trainer.config.output_dir)
    
    result = evaluator.evaluate()
    
    logger.info(f"Evaluation complete!")
    for metric, value in result.metrics.items():
        logger.info(f"  - {metric}: {value:.4f}")
    
    return result


def register_model(trainer, train_result, eval_result):
    """注册模型到仓库"""
    logger.info("=== Step 5: Registering model ===")
    
    from models.deployment.model_registry import load_registry, ModelInfo
    
    registry = load_registry(sync=True)
    
    model_info = ModelInfo(
        model_name="jsx-code-generator",
        model_version="1.0.0",
        model_type="jsx_code",
        model_path=train_result.model_path,
        base_model=trainer.jsx_config.base_model_path,
        training_method="lora",
        params_million=train_result.params_million,
        train_samples=len(trainer._train_dataset) if trainer._train_dataset else 0,
        eval_metrics=eval_result.metrics if eval_result else {},
        cost_effectiveness=eval_result.cost_effectiveness if eval_result else 0.0,
        training_time_hours=train_result.training_time_seconds / 3600,
        training_cost_usd=train_result.cost_estimate_usd,
        status="staging",
        description="AE JSX代码生成小模型，基于TinyLlama-1.1B + LoRA微调，约50M可训练参数，支持输入风格描述输出AE JSX代码",
        tags=["jsx", "code-generation", "after-effects", "lora", "tinyllama"],
    )
    
    model_id = registry.register_model(model_info)
    logger.info(f"Model registered: {model_id}")
    
    return model_id


def test_generation(trainer):
    """测试代码生成"""
    logger.info("=== Step 6: Testing code generation ===")
    
    test_instructions = [
        "为图层添加wiggle表达式动画",
        "创建新合成，宽度1920高度1080",
        "添加发光效果，颜色红色，半径20",
        "为文字图层添加打字机效果",
    ]
    
    for instruction in test_instructions:
        logger.info(f"\n--- Prompt: {instruction} ---")
        jsx_code = trainer.generate_jsx(instruction, max_length=256)
        logger.info(f"Generated JSX:\n{jsx_code[:300]}...")


def main():
    """主流程"""
    try:
        dataset_path, total_samples = prepare_dataset()
        
        train_path, val_path, test_path = split_dataset(dataset_path)
        
        trainer, train_result = train_model(train_path, val_path)
        
        eval_result = evaluate_model(trainer, test_path)
        
        model_id = register_model(trainer, train_result, eval_result)
        
        test_generation(trainer)
        
        logger.info("\n=== All steps completed successfully! ===")
        logger.info(f"Model: {model_id}")
        logger.info(f"Location: {train_result.model_path}")
        logger.info(f"Params: {train_result.params_million:.2f}M")
        
    except Exception as e:
        logger.error(f"Training pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()