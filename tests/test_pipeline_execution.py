import os
import sys
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ae_agent_pipeline import AEAgentPipeline, ExecutionResult, PlanningResult


def test_pipeline_execution_with_mock():
    """测试使用模拟MCP客户端的执行流程"""
    pipeline = AEAgentPipeline()
    
    mock_client = Mock()
    mock_client.send_command.return_value = {"success": True, "status": "success"}
    mock_client.clear_result = Mock()
    
    planning = PlanningResult()
    planning.composition = {
        "name": "Test_Comp",
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30
    }
    planning.layers = []
    planning.effects = []
    planning.keyframes = []
    planning.transitions = []
    planning.execution_order = ["createComposition"]
    
    with patch('ae_mcp_client.AECommandClient', return_value=mock_client):
        result = pipeline.execute(planning)
    
    assert result.success is True
    assert mock_client.send_command.called
    assert result.steps_completed > 0

def test_pipeline_execution_with_layers_and_effects():
    """测试包含图层和效果的执行流程"""
    pipeline = AEAgentPipeline()
    
    mock_client = Mock()
    mock_client.send_command.return_value = {"success": True, "status": "success"}
    mock_client.clear_result = Mock()
    
    planning = PlanningResult()
    planning.composition = {
        "name": "Full_Test",
        "width": 1920,
        "height": 1080,
        "duration": 10,
        "frameRate": 30
    }
    planning.layers = [
        {"name": "Video1", "type": "footage", "source": "/path/v1.mp4", "startTime": 0, "duration": 5},
        {"name": "Video2", "type": "footage", "source": "/path/v2.mp4", "startTime": 5, "duration": 5}
    ]
    planning.effects = [
        {"layerName": "Video1", "effectName": "ADBE Glo2", "settings": {"Radius": 50}}
    ]
    planning.keyframes = [
        {"layerName": "Video1", "propertyName": "Opacity", "time": 0, "value": 0, "easeType": "easeInOut"},
        {"layerName": "Video1", "propertyName": "Opacity", "time": 1, "value": 100, "easeType": "easeInOut"}
    ]
    planning.transitions = []
    planning.execution_order = ["createComposition", "importFootage", "placeFootageInComp", "applyEffects", "setKeyframes", "renderVideo"]
    
    with patch('ae_mcp_client.AECommandClient', return_value=mock_client):
        result = pipeline.execute(planning)
    
    assert result.success is True
    assert mock_client.send_command.call_count > 5

def test_pipeline_execution_failure():
    """测试执行失败的情况"""
    pipeline = AEAgentPipeline()
    
    mock_client = Mock()
    mock_client.send_command.return_value = {"success": False, "status": "error", "message": "Test error"}
    mock_client.clear_result = Mock()
    
    planning = PlanningResult()
    planning.composition = {
        "name": "Fail_Test",
        "width": 1920,
        "height": 1080,
        "duration": 5,
        "frameRate": 30
    }
    planning.layers = []
    planning.effects = []
    planning.keyframes = []
    planning.transitions = []
    planning.execution_order = ["createComposition"]
    
    with patch('ae_mcp_client.AECommandClient', return_value=mock_client):
        result = pipeline.execute(planning)
    
    assert result.success is False
    assert result.error_message is not None
    assert len(result.error_message) > 0

def test_execution_result_type():
    """测试execute返回类型正确"""
    pipeline = AEAgentPipeline()
    
    mock_client = Mock()
    mock_client.send_command.return_value = {"success": True, "status": "success"}
    mock_client.clear_result = Mock()
    
    planning = PlanningResult()
    planning.composition = {"name": "TypeTest", "width": 1920, "height": 1080, "duration": 3, "frameRate": 30}
    planning.layers = []
    planning.effects = []
    planning.keyframes = []
    planning.transitions = []
    planning.execution_order = ["createComposition"]
    
    with patch('ae_mcp_client.AECommandClient', return_value=mock_client):
        result = pipeline.execute(planning)
    
    assert isinstance(result, ExecutionResult)
    assert hasattr(result, 'success')
    assert hasattr(result, 'steps_completed')
    assert hasattr(result, 'total_steps')
    assert hasattr(result, 'error_message')
    assert hasattr(result, 'output_path')
