"""
Param optimization model evaluation script
"""
import os
import sys
import json
import logging
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

logger = logging.getLogger(__name__)


def main():
    from models.data.param_optim_dataset import ParamOptimDataset, DatasetConfig, STYLE_LABELS
    from models.training.param_optim_trainer import ParamOptimTrainer, TrainingConfig

    logger.info('===== Evaluation Started =====')

    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    dataset_config = DatasetConfig(
        dataset_name='param-optim-dataset',
        data_path=os.path.join(project_root, 'config', 'effect_presets.json'),
        max_samples=None,
        test_split_ratio=0.1,
        val_split_ratio=0.1,
        seed=42,
        data_augmentation=False,
        filter_invalid=True,
    )

    dataset = ParamOptimDataset(dataset_config)
    stats = dataset.prepare()

    test_data = dataset.get_test_data()

    model_path = os.path.join(project_root, 'models', 'output', 'param-optimizer', 'best_model.pt')

    if not os.path.exists(model_path):
        logger.error(f'Model not found: {model_path}')
        return

    training_config = TrainingConfig(
        model_name='param-optimizer',
        output_dir=os.path.join(project_root, 'models', 'output', 'param-optimizer'),
    )

    trainer = ParamOptimTrainer.load_model(model_path, training_config)

    logger.info(f'Test samples: {len(test_data)}')

    logger.info('===== Overall Evaluation =====')
    trainer.load_dataset(test_data, test_data)
    metrics = trainer.evaluate()

    logger.info('Overall metrics:')
    logger.info(f'  MSE: {metrics.get("mse", 0):.6f}')
    logger.info(f'  MAE: {metrics.get("mae", 0):.6f}')
    logger.info(f'  R2: {metrics.get("r2", 0):.4f}')
    logger.info(f'  RMSE: {metrics.get("rmse", 0):.6f}')

    logger.info('===== Style Evaluation =====')
    style_metrics = {}

    for style_label in STYLE_LABELS[:10]:
        style_data = [s for s in test_data if s['style_label'] == style_label]
        if len(style_data) < 5:
            continue

        trainer.load_dataset(style_data, style_data)
        style_metric = trainer.evaluate()
        style_metrics[style_label] = style_metric

        logger.info(f'Style: {style_label} (samples: {len(style_data)})')
        logger.info(f'  MSE: {style_metric.get("mse", 0):.6f}')
        logger.info(f'  MAE: {style_metric.get("mae", 0):.6f}')
        logger.info(f'  R2: {style_metric.get("r2", 0):.4f}')

    logger.info('===== Prediction Example =====')
    sample = test_data[0]
    input_vec = sample['input_vector']
    prediction = trainer.predict(input_vec)

    logger.info(f'Example - Effect: {sample["effect_name"]}')
    logger.info(f'Example - Style: {sample["style_label"]}')
    logger.info('Base params (normalized):')
    for param_name, value in sample['normalized_base'].items():
        logger.info(f'  {param_name}: {value:.4f}')

    logger.info('Target params (normalized):')
    for param_name, value in sample['normalized_optimized'].items():
        logger.info(f'  {param_name}: {value:.4f}')

    logger.info('Predicted params (normalized):')
    param_names = dataset.get_param_names()
    for i, param_name in enumerate(param_names):
        if param_name in sample['normalized_optimized']:
            logger.info(f'  {param_name}: {prediction[i]:.4f} (target: {sample["normalized_optimized"][param_name]:.4f})')

    logger.info('===== Evaluation Report =====')
    report = {
        'model_name': 'param-optimizer',
        'model_version': '1.0.0',
        'evaluation_time': __import__('time').strftime('%Y-%m-%d %H:%M:%S'),
        'test_samples': len(test_data),
        'overall_metrics': metrics,
        'style_metrics': style_metrics,
        'param_names': dataset.get_param_names(),
        'input_dim': dataset.get_input_dim(),
        'output_dim': dataset.get_output_dim(),
    }

    report_path = os.path.join(project_root, 'models', 'output', 'param-optimizer', 'evaluation_report.json')
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f'Report saved to: {report_path}')
    logger.info('===== Evaluation Complete =====')


if __name__ == '__main__':
    main()
