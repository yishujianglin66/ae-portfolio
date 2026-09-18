"""
Import重定向兼容层
确保旧代码中的 import xxx 仍然能正常工作，即使文件已迁移到子目录
"""
import importlib.util
import os
import sys

# 递归保护：记录正在加载中的模块，防止循环重定向导致无限递归
_LOADING = set()

# 重定向映射表：旧模块名 -> 新模块路径
_REDIRECT_MAP = {
    # integrations/
    "adobe_suite_integration": "integrations.adobe_suite_integration",
    "phase2_real_audio_integration": "integrations.phase2_real_audio_integration",
    "workflow_batch_integration": "integrations.workflow_batch_integration",
    "mediapipe_integration": "integrations.mediapipe_integration",
    
    # bridges/
    "adobe_universal_bridge": "bridges.adobe_universal_bridge",
    
    # ae/
    "ae_post_processing": "ae.ae_post_processing",
    "ae_ts_compiler_client": "ae.ae_ts_compiler_client",
    
    # api/
    "ai_chat_api": "api.ai_chat_api",
    "camera_classifier_api": "api.camera_classifier_api",
    "integrator_api": "api.integrator_api",
    "toolchain_api": "api.toolchain_api",
    # 注意(2026-08-26): 不得将 test_* 模块名加入重定向表！
    # pytest 收集 tests/test_xxx.py 时使用同名裸模块名，重定向器会抢先加载
    # scripts/ 下的同名文件，造成 import file mismatch 收集错误。
    # 已移除: test_camera_api / test_camera_classifier / test_effect_params / test_hierarchical_architecture
    
    # core/
    "audio_edit_engine": "core.audio_edit_engine",
    "beat_orchestrator": "core.beat_orchestrator",
    "clarification_engine": "core.clarification_engine",
    "effect_composition_engine": "core.effect_composition_engine",
    "filter_engine": "core.filter_engine",
    "layer_orchestrator": "core.layer_orchestrator",
    "puppet_style_engine": "core.puppet_style_engine",
    "puppet_workflow_orchestrator": "core.puppet_workflow_orchestrator",
    "scene_3d_orchestrator": "core.scene_3d_orchestrator",
    "scene_orchestrator": "core.scene_orchestrator",
    "text_animation_engine": "core.text_animation_engine",
    "transition_engine": "core.transition_engine",
    
    # scripts/
    "demo_camera_classification": "scripts.demo_camera_classification",
    "optimize_inference_performance": "scripts.optimize_inference_performance",
    "reverse_engineer_pipeline": "scripts.reverse_engineer_pipeline",
    "validate_camera_classifier": "scripts.validate_camera_classifier",
    "adobe_mcp_manager": "bridges.adobe_mcp_manager",
    "adobe_mcp_server": "bridges.adobe_mcp_server",
    "ae_tools_mcp_server": "ae.ae_tools_mcp_server",
    "aep_binary_parser": "ae.aep_binary_parser",
    "analyze_clip": "scripts.analyze_clip",
    "asset_manager": "media.asset_manager",
    "au_bridge_client": "bridges.au_bridge_client",
    "audio-analyzer": "audio.audio-analyzer",
    "audio_analyzer_enhanced": "audio.audio_analyzer_enhanced",
    "audio_analyzer_librosa": "audio.audio_analyzer_librosa",
    "audio_driven_effects": "audio.audio_driven_effects",
    "color_grading_applier": "style.color_grading_applier",
    "distributed_scheduler": "pipeline.distributed_scheduler",
    "effect_composer": "effects.effect_composer",
    "effect_description_parser": "effects.effect_description_parser",
    "effect_generators": "effects.effect_generators",
    "effect_knowledge_graph": "effects.effect_knowledge_graph",
    "effect_name_map": "effects.effect_name_map",
    "effect_registry": "effects.effect_registry",
    "effect_reproducer": "effects.effect_reproducer",
    "examples_ae_to_davinci": "scripts.examples_ae_to_davinci",
    "examples_davinci_color_grading": "scripts.examples_davinci_color_grading",
    "examples_minimal_creative_loop": "scripts.examples_minimal_creative_loop",
    "expression_library": "effects.expression_library",
    "frame_enhancement_pipeline": "video.frame_enhancement_pipeline",
    "generate_3d_presets": "scripts.generate_3d_presets",
    "kb_loader": "knowledge.kb_loader",
    "kb_qa": "knowledge.kb_qa",
    "kb_scanner": "knowledge.kb_scanner",
    "knowledge_mcp_server": "knowledge.knowledge_mcp_server",
    "knowledge_searcher": "knowledge.knowledge_searcher",
    "mcp_bridge_client": "bridges.mcp_bridge_client",
    "media_metadata_db": "media.media_metadata_db",
    "media_preprocessor": "media.media_preprocessor",
    "model_router": "models.model_router",
    "parameter_mapper": "utils.parameter_mapper",
    "parameter_optimizer": "utils.parameter_optimizer",
    "plugin_system": "tools.plugin_system",
    "pr_bridge_client": "bridges.pr_bridge_client",
    "premiere_mcp_client": "bridges.premiere_mcp_client",
    "ps_bridge_client": "bridges.ps_bridge_client",
    "render_reference_style": "style.render_reference_style",
    "render_style_migration": "style.render_style_migration",
    "resource_manager": "utils.resource_manager",
    "result_verifier": "utils.result_verifier",
    "scene_detector": "scene.scene_detector",
    "silhouette_executor": "silhouette.silhouette_executor",
    "silhouette_fx_emulator": "silhouette.silhouette_fx_emulator",
    "style_migrator": "style.style_migrator",
    "style_template_library": "style.style_template_library",
    "subtitle_burner": "video.subtitle_burner",
    "tool_executor": "tools.tool_executor",
    "toolchain_manager": "tools.toolchain_manager",
    "transition_map": "transition.transition_map",
    "transition_rebuilder": "transition.transition_rebuilder",
    "unified_asset_manager": "media.unified_asset_manager",
    "unified_mcp_server_v2": "bridges.unified_mcp_server_v2",
    "vector_index_faiss": "knowledge.vector_index_faiss",
    "video_generator": "video.video_generator",
    "video_quality_assessor": "video.video_quality_assessor",
    "ai_agent": "ai.ai_agent",
    "visual_analysis": "ai.visual_analysis",
    "visual_content_analyzer": "ai.visual_content_analyzer",
    "workflow_dsl": "tools.workflow_dsl",
    "ae_bridge_base": "ae.ae_bridge_base",
    "ae_command_generator": "ae.ae_command_generator",
    "ae_composition_presets": "ae.ae_composition_presets",
    "ae_extension_integrator": "ae.ae_extension_integrator",
    "ae_mcp_client": "ae.ae_mcp_client",
    "ae_process_manager": "ae.ae_process_manager",
    "ae_smart_orchestrator": "ae.ae_smart_orchestrator",
    "auth_system": "auth.auth_system",
    "auto_downloader": "utils.auto_downloader",
    "batch_queue": "pipeline.batch_queue",
    "beat_keyframe_mapper": "core.beat_keyframe_mapper",
    "beat_sync_generator": "core.beat_sync_generator",
    "bilibili_creator_analyzer": "analysis.bilibili_creator_analyzer",
    "branch_diff_analysis": "analysis.branch_diff_analysis",
    "career_growth_analyzer": "analysis.career_growth_analyzer",
    "cinematic_intelligence": "core.cinematic_intelligence",
    "deploy_nvidia_agent": "utils.deploy_nvidia_agent",
    "failure_recovery": "feedback.failure_recovery",
    "feedback_loop_manager": "feedback.feedback_loop_manager",
    "feedback_manager": "feedback.feedback_manager",
    "get_git_log": "utils.get_git_log",
    "hybrid_coordinator": "core.hybrid_coordinator",
    "image_analyzer": "analysis.image_analyzer",
    "image_handler": "analysis.image_handler",
    "install_ffmpeg": "utils.install_ffmpeg",
    "intent_router": "core.intent_router",
    "intent_to_report": "core.intent_to_report",
    "keyframe_animation_generator": "core.keyframe_animation_generator",
    "learning_loop": "learning.learning_loop",
    "multimodal_director": "core.multimodal_director",
    "nlu_parser": "core.nlu_parser",
    "persistent_learning_loop": "learning.persistent_learning_loop",
    "puppet_auto_processor": "puppet.puppet_auto_processor",
    "report_to_ops": "tasks.report_to_ops",
    "setup_premiere_mcp": "utils.setup_premiere_mcp",
    "stage_3d_director": "core.stage_3d_director",
    "task_persistence": "tasks.task_persistence",
    "text_animator": "core.text_animator",
    "training_logger": "learning.training_logger",
    "training_state_manager": "learning.training_state_manager",
    "unified_tool_integrator": "tools.unified_tool_integrator",
    "vocabulary_map": "core.vocabulary_map",
}


class _ImportRedirector:
    """Import重定向钩子"""
    
    def find_module(self, fullname, path=None):
        """如果模块在重定向表中，返回self作为finder"""
        # 递归保护：正在加载中的模块不再重定向，避免无限递归
        if fullname in _REDIRECT_MAP and fullname not in _LOADING:
            return self
        return None
    
    def load_module(self, fullname):
        """加载重定向的模块"""
        if fullname in sys.modules:
            return sys.modules[fullname]
        
        # 递归保护：标记为加载中，防止子模块导入时再次触发同一重定向
        _LOADING.add(fullname)
        new_name = _REDIRECT_MAP[fullname]
        try:
            module = importlib.import_module(new_name)
            sys.modules[fullname] = module
            return module
        except ImportError as e:
            raise ImportError(
                f"Cannot redirect '{fullname}' to '{new_name}': {e}"
            ) from e
        finally:
            _LOADING.discard(fullname)


def install_redirect():
    """安装import重定向钩子"""
    # 检查是否已安装
    for hook in sys.meta_path:
        if isinstance(hook, _ImportRedirector):
            return  # 已安装
    
    # 安装新钩子
    sys.meta_path.insert(0, _ImportRedirector())
    print(f"[import_redirect] 已安装重定向钩子，共 {len(_REDIRECT_MAP)} 条规则")


def get_redirect_info():
    """获取重定向信息"""
    return {
        "total_rules": len(_REDIRECT_MAP),
        "rules": _REDIRECT_MAP.copy()
    }


# 自动安装
install_redirect()
