"""
Param optimization model training script
"""
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('param_optim_training.log'),
        logging.StreamHandler(),
    ]
)

logger = logging.getLogger(__name__)


def main():
    from models.configs.param_optim_config import ParamOptimConfig
    from models.data.param_optim_dataset import DatasetConfig, ParamOptimDataset
    from models.deployment.model_registry import ModelInfo, load_registry
    from models.training.param_optim_trainer import ParamOptimTrainer, TrainingConfig

    logger.info('===== Training Started =====')

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    dataset_config = DatasetConfig(
        dataset_name='param-optim-dataset',
        data_path=os.path.join(project_root, 'config', 'effect_presets.json'),
        max_samples=None,
        test_split_ratio=0.1,
        val_split_ratio=0.1,
        seed=42,
        data_augmentation=True,
        filter_invalid=True,
    )

    dataset = ParamOptimDataset(dataset_config)
    stats = dataset.prepare()

    logger.info(f'Dataset: total={stats.total_samples}, train={stats.train_samples}, val={stats.val_samples}, test={stats.test_samples}')
    logger.info(f'Invalid: {stats.invalid_samples}, Augmented: {stats.augmented_samples}')

    train_data = dataset.get_train_data()
    val_data = dataset.get_val_data()
    test_data = dataset.get_test_data()

    logger.info(f'Input dim: {dataset.get_input_dim()}')
    logger.info(f'Output dim: {dataset.get_output_dim()}')
    logger.info(f'Param names: {dataset.get_param_names()}')

    param_optim_config = ParamOptimConfig()
    training_config = TrainingConfig(**param_optim_config.get_training_config_kwargs())

    output_dir = os.path.join(project_root, 'models', 'output', 'param-optimizer')
    training_config.output_dir = output_dir
    training_config.epochs = 30
    training_config.batch_size = 32
    training_config.learning_rate = 3e-4
    training_config.logging_steps = 10
    training_config.save_steps = 50
    training_config.eval_steps = 50

    os.makedirs(output_dir, exist_ok=True)

    trainer = ParamOptimTrainer(training_config)
    trainer.load_dataset(train_data, val_data)
    trainer.load_base_model()

    logger.info('===== Start Training =====')
    start_time = time.time()

    result = trainer.train()

    training_time = time.time() - start_time

    logger.info('===== Training Complete =====')
    logger.info(f'Model path: {result.model_path}')
    logger.info(f'Total steps: {result.total_steps}')
    logger.info(f'Total epochs: {result.total_epochs}')
    logger.info(f'Train loss: {result.train_loss:.6f}')
    logger.info(f'Eval loss: {result.eval_loss:.6f}')
    logger.info(f'Params: {result.params_million:.2f}M')
    logger.info(f'Training time: {training_time:.2f}s')
    logger.info(f'Cost: ${result.cost_estimate_usd:.2f}')

    logger.info('Metrics:')
    for metric, value in result.eval_metrics.items():
        logger.info(f'  {metric}: {value:.6f}')

    save_path = trainer.save_model(os.path.join(output_dir, 'deploy'))
    logger.info(f'Deploy model: {save_path}')

    logger.info('===== Test Evaluation =====')
    trainer.load_dataset(test_data, test_data)
    test_metrics = trainer.evaluate()

    logger.info('Test metrics:')
    for metric, value in test_metrics.items():
        logger.info(f'  {metric}: {value:.6f}')

    logger.info('===== Register Model =====')
    registry = load_registry(sync=True)

    model_info = ModelInfo(
        model_name='param-optimizer',
        model_version='1.0.0',
        model_type='param_optim',
        model_path=save_path,
        base_model='mlp-10m',
        training_method='full_finetune',
        params_million=result.params_million,
        train_samples=stats.train_samples,
        eval_metrics={**result.eval_metrics, **test_metrics},
        training_time_hours=training_time / 3600.0,
        training_cost_usd=result.cost_estimate_usd,
        status='staging',
        description='AE effect parameter optimization model',
        tags=['parameter-optimization', 'AE', 'regression', 'mlp', '10m-params'],
        metadata={
            'input_dim': dataset.get_input_dim(),
            'output_dim': dataset.get_output_dim(),
            'num_styles': dataset.get_num_styles(),
            'param_names': dataset.get_param_names(),
        },
    )

    model_info.cost_effectiveness = result.params_million * 0.5 + test_metrics.get('r2', 0) * 50
    model_id = registry.register_model(model_info)
    logger.info(f'Registered: {model_id}')

    logger.info('===== Done =====')


if __name__ == '__main__':
    main()
