"""Tests for TextEffectService."""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.text_effect_service import TextEffectService
from src.engines.base import EngineResult


@pytest.fixture
def mock_ae_engine():
    """Mock AE Engine for testing."""
    engine = MagicMock()
    engine.run_script = AsyncMock()
    return engine


@pytest.fixture
def text_service(mock_ae_engine):
    """TextEffectService instance with mocked AE engine."""
    return TextEffectService(ae_engine=mock_ae_engine)


class TestTextEffectService:
    """Test suite for TextEffectService."""

    def test_init(self, text_service):
        """Test service initialization."""
        assert text_service.ae is not None
        assert text_service._verified is False

    def test_font_presets(self, text_service):
        """Test font presets are loaded."""
        assert len(text_service.FONT_PRESETS) == 8
        assert "cinematic" in text_service.FONT_PRESETS
        assert "epic" in text_service.FONT_PRESETS
        assert text_service.FONT_PRESETS["cinematic"]["font"] == "Impact"

    def test_hex_to_rgb(self, text_service):
        """Test HEX to RGB conversion."""
        # Test pure red
        rgb = text_service._hex_to_rgb("#FF0000")
        assert rgb == pytest.approx((1.0, 0.0, 0.0), rel=1e-3)

        # Test pure green
        rgb = text_service._hex_to_rgb("#00FF00")
        assert rgb == pytest.approx((0.0, 1.0, 0.0), rel=1e-3)

        # Test pure blue
        rgb = text_service._hex_to_rgb("#0000FF")
        assert rgb == pytest.approx((0.0, 0.0, 1.0), rel=1e-3)

        # Test without #
        rgb = text_service._hex_to_rgb("FFFFFF")
        assert rgb == pytest.approx((1.0, 1.0, 1.0), rel=1e-3)

    def test_rgb_to_jsx_array(self, text_service):
        """Test RGB to JSX array conversion."""
        jsx = text_service._rgb_to_jsx_array((1.0, 0.5, 0.0))
        assert jsx == "[1.000, 0.500, 0.000]"

        jsx = text_service._rgb_to_jsx_array((0.0, 0.0, 0.0))
        assert jsx == "[0.000, 0.000, 0.000]"

    @pytest.mark.asyncio
    async def test_create_3d_title(self, text_service, mock_ae_engine):
        """Test 3D title creation."""
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success","layer_name":"TXT_Test"}'}
        )

        result = await text_service.create_3d_title(
            comp_name="Main Comp",
            text="Test",
            position=(960, 540),
            style="epic3D",
            font_size=120,
        )

        assert result.success is True
        mock_ae_engine.run_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_glow_layer(self, text_service, mock_ae_engine):
        """Test glow layer application."""
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success","layer_name":"GLOW_TXT_Test"}'}
        )

        result = await text_service.apply_glow_layer(
            comp_name="Main Comp",
            text_layer_index=0,
            glow_color="#00FFFF",
            glow_intensity=0.8,
        )

        assert result.success is True
        mock_ae_engine.run_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_rgb_separation(self, text_service, mock_ae_engine):
        """Test RGB separation application."""
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success","red_layer":"RGB_R_Test","cyan_layer":"RGB_C_Test"}'}
        )

        result = await text_service.apply_rgb_separation(
            comp_name="Main Comp",
            text_layer_index=0,
            offset_x=6,
        )

        assert result.success is True
        mock_ae_engine.run_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_gradient_overlay(self, text_service, mock_ae_engine):
        """Test gradient overlay application."""
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success","layer_name":"GRAD_Test"}'}
        )

        result = await text_service.apply_gradient_overlay(
            comp_name="Main Comp",
            text_layer_index=0,
            gradient_colors=["#FF0000", "#0000FF"],
        )

        assert result.success is True
        mock_ae_engine.run_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_gradient_overlay_insufficient_colors(self, text_service):
        """Test gradient overlay with insufficient colors."""
        result = await text_service.apply_gradient_overlay(
            comp_name="Main Comp",
            text_layer_index=0,
            gradient_colors=["#FF0000"],  # Only one color
        )

        assert result.success is False
        assert "at least 2 colors" in result.error

    @pytest.mark.asyncio
    async def test_create_full_title_system(self, text_service, mock_ae_engine):
        """Test full title system creation."""
        # Mock all layer creation calls
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success","layer_name":"test"}'}
        )

        result = await text_service.create_full_title_system(
            comp_name="Main Comp",
            text="Test Title",
            position=(960, 540),
            style="epic3D",
        )

        assert result.success is True
        assert result.metadata["text"] == "Test Title"
        assert result.metadata["layers_created"] == 5
        assert len(result.metadata["architecture"]) == 5

    @pytest.mark.asyncio
    async def test_apply_neon_effect(self, text_service, mock_ae_engine):
        """Test neon effect application."""
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success"}'}
        )

        result = await text_service.apply_neon_effect(
            comp_name="Main Comp",
            text_layer_index=0,
            glow_size=25,
            glow_intensity=1.5,
        )

        assert result.success is True
        mock_ae_engine.run_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_apply_text_animation(self, text_service, mock_ae_engine):
        """Test text animation application."""
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success"}'}
        )

        result = await text_service.apply_text_animation(
            comp_name="Main Comp",
            text_layer_index=0,
            animation_type="typewriter",
            duration=1.0,
        )

        assert result.success is True
        mock_ae_engine.run_script.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_layer_info(self, text_service, mock_ae_engine):
        """Test layer info retrieval."""
        mock_ae_engine.run_script.return_value = EngineResult(
            success=True,
            metadata={"stdout": '{"status":"success","layer_name":"Test","index":0}'}
        )

        info = await text_service.get_layer_info(
            comp_name="Main Comp",
            layer_name="Test",
        )

        assert info["status"] == "success"
        assert info["layer_name"] == "Test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])