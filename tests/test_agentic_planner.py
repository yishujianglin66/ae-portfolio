from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.multi_agent_orchestrator import (
    AgenticPlanner,
    AgentRole,
    PlannerParseError,
    SubTaskPlan,
)


GOOD_PLAN_JSON = json.dumps([
    {
        'task_id': 'style-1',
        'description': '分析输入视频的节奏与剪辑风格',
        'agent_role': 'STYLE_ANALYSIS',
        'dependencies': [],
        'input_hints': {'focus': 'beat + transition'},
    },
    {
        'task_id': 'code-2',
        'description': '基于风格生成 AE JSX 脚本',
        'agent_role': 'CODE_GENERATION',
        'dependencies': ['style-1'],
        'input_hints': {},
    },
    {
        'task_id': 'review-final',
        'description': '质量检查脚本与风格匹配度',
        'agent_role': 'QUALITY_REVIEW',
        'dependencies': ['style-1', 'code-2'],
        'input_hints': {},
    },
])


REFLECT_PLAN_JSON = json.dumps([
    {
        'task_id': 'style-1',
        'description': '分析输入视频的节奏',
        'agent_role': 'STYLE_ANALYSIS',
        'dependencies': [],
        'input_hints': {},
    },
    {
        'task_id': 'param-2',
        'description': '优化脚本参数',
        'agent_role': 'PARAMETER_OPTIMIZATION',
        'dependencies': ['style-1'],
        'input_hints': {},
    },
    {
        'task_id': 'code-3',
        'description': '生成 AE JSX 脚本',
        'agent_role': 'CODE_GENERATION',
        'dependencies': ['style-1', 'param-2'],
        'input_hints': {},
    },
    {
        'task_id': 'review-final',
        'description': '最终质量检查',
        'agent_role': 'QUALITY_REVIEW',
        'dependencies': ['style-1', 'param-2', 'code-3'],
        'input_hints': {},
    },
])


class DummyResponse:
    def __init__(self, content):
        self.content = content


class TestPlannerParse:
    @pytest.mark.asyncio
    @patch('core.multi_agent_orchestrator.LLMGateway')
    async def test_plan_parses_valid_json(self, MockLLM):
        mock_llm = MagicMock()
        mock_llm.chat_with_routing = AsyncMock(return_value=DummyResponse(GOOD_PLAN_JSON))
        planner = AgenticPlanner(llm_gateway=mock_llm)

        result = await planner.plan('做一个燃向剪辑')

        assert isinstance(result, list)
        assert len(result) == 3
        for s in result:
            assert isinstance(s, SubTaskPlan)
            assert s.agent_role in (
                AgentRole.STYLE_ANALYSIS,
                AgentRole.CODE_GENERATION,
                AgentRole.PARAMETER_OPTIMIZATION,
                AgentRole.QUALITY_REVIEW,
            )
        assert result[0].task_id == 'style-1'
        assert result[0].dependencies == []
        assert result[1].dependencies == ['style-1']


class TestPlannerParseBadJSON:
    @pytest.mark.asyncio
    @patch('core.multi_agent_orchestrator.LLMGateway')
    async def test_bad_json_raises(self, MockLLM):
        dirty = '`json\nnot a json\n`'
        mock_llm = MagicMock()
        mock_llm.chat_with_routing = AsyncMock(return_value=DummyResponse(dirty))
        planner = AgenticPlanner(llm_gateway=mock_llm)

        with pytest.raises(PlannerParseError):
            await planner.plan('测试任务')


def _make_orchestrator_mock(fail_first: bool = False):
    mock_orch = MagicMock()
    call_count = {}

    async def _fake_run_and_collect(global_input=None):
        key = 'run'
        call_count[key] = call_count.get(key, 0) + 1
        if fail_first and call_count[key] == 1:
            return {
                'style-1': {'success': True, 'data': {'tags': ['cinematic']}},
                'code-2': {'success': False, 'error': 'SyntaxError in JSX'},
                'review-final': {'success': False, 'error': 'skipped'},
            }
        # 成功结果：覆盖所有新旧 plan 的 task_id
        return {
            'style-1': {'success': True, 'data': {'tags': ['cinematic']}},
            'code-2': {'success': True, 'data': {'jsx_code': '// ok'}},
            'param-2': {'success': True, 'data': {'params': {'scale': 1.0}}},
            'code-3': {'success': True, 'data': {'jsx_code': '// ok v2'}},
            'review-final': {'success': True, 'data': {'passed': True}},
        }

    mock_orch.run_and_collect = AsyncMock(side_effect=_fake_run_and_collect)
    mock_orch.register_subtasks = MagicMock()
    mock_orch._tasks_def = []
    mock_orch._task_dependencies = {}
    mock_orch._task_dependents = {}
    mock_orch._completed_tasks = set()
    mock_orch._failed_tasks = set()
    return mock_orch


class TestAutoExecuteHappy:
    @pytest.mark.asyncio
    @patch('core.multi_agent_orchestrator.LLMGateway')
    async def test_happy_path_success(self, MockLLM):
        mock_llm = MagicMock()
        mock_llm.chat_with_routing = AsyncMock(return_value=DummyResponse(GOOD_PLAN_JSON))
        MockLLM.return_value = mock_llm
        mock_orch = _make_orchestrator_mock()

        planner = AgenticPlanner(llm_gateway=mock_llm, orchestrator=mock_orch, max_reflect_attempts=2)
        success, results, trace = await planner.auto_execute('测试高层任务')

        assert success is True
        assert len(trace) >= 3
        actions = [s.action for s in trace]
        assert 'decompose' in actions
        assert 'call_agent' in actions
        assert 'finalize' in actions
        assert results.get('style-1', {}).get('success') is True
        assert mock_orch.register_subtasks.called


class TestAutoExecuteReflect:
    @pytest.mark.asyncio
    @patch('core.multi_agent_orchestrator.LLMGateway')
    async def test_reflect_then_success(self, MockLLM):
        plan_resp = DummyResponse(GOOD_PLAN_JSON)
        reflect_resp = DummyResponse(f'反思总结：代码生成失败是因为缺少前置参数\n{REFLECT_PLAN_JSON}')
        mock_llm = MagicMock()
        # 多备几个响应，避免 side_effect 耗尽
        mock_llm.chat_with_routing = AsyncMock(side_effect=[
            plan_resp, reflect_resp, reflect_resp, plan_resp,
        ])
        MockLLM.return_value = mock_llm

        mock_orch = _make_orchestrator_mock(fail_first=True)
        planner = AgenticPlanner(llm_gateway=mock_llm, orchestrator=mock_orch, max_reflect_attempts=2)

        success, results, trace = await planner.auto_execute('测试任务')
        actions = [s.action for s in trace]

        # 至少有 1 次 reflect（最多不超过 max_reflect_attempts）
        assert actions.count('reflect') >= 1
        assert actions.count('reflect') <= 2
        assert 'decompose' in actions
        assert actions.count('call_agent') >= 2
        assert success is True
        assert mock_llm.chat_with_routing.await_count >= 2
