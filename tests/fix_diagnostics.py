"""增强 _gen_clip_color_lua 诊断输出"""
import ast

p = r'c:\Users\Administrator\Desktop\AE-Knowledge-Vault\integrations\davinci_fuscript.py'
with open(p, 'r', encoding='utf-8') as f:
    content = f.read()

# Find function boundaries
idx = content.find('def _gen_clip_color_lua(')
if idx < 0:
    print('ERROR: function not found')
    exit(1)

end_idx = content.find('\n    def _build_pipeline_lua(', idx)
if end_idx < 0:
    print('ERROR: end not found')
    exit(1)

new_func = '''    def _gen_clip_color_lua(
        self,
        lua_lut: str,
        config: ColorGradeConfig,
        indent: str = "                ",
        use_active_lut: bool = False,
    ) -> str:
        """生成单个片段的调色 Lua 代码（LUT + Fusion，含详细诊断）"""
        lines = []
        # LUT 应用
        if use_active_lut:
            if lua_lut:
                lines.append(f'{indent}if activeLUT and activeLUT ~= "" then')
                lines.append(f'{indent}    local lutOk, lutErr = pcall(function() item:SetLUT(activeLUT) end)')
                lines.append(f'{indent}    if lutOk then print("    [OK] SetLUT applied") else print("    [FAIL] SetLUT: " .. tostring(lutErr)) end')
                lines.append(f'{indent}else')
                lines.append(f'{indent}    print("    [SKIP] No activeLUT")')
                lines.append(f'{indent}end')
        else:
            if lua_lut:
                lines.append(f'{indent}local lutOk, lutErr = pcall(function() item:SetLUT("{lua_lut}") end)')
                lines.append(f'{indent}if lutOk then print("    [OK] SetLUT applied") else print("    [FAIL] SetLUT: " .. tostring(lutErr)) end')
            else:
                lines.append(f'{indent}print("    [SKIP] No LUT path")')
        # Fusion 调色
        if config.brightness != 1.0 or config.contrast != 1.0 or config.saturation != 1.0:
            brightness = config.brightness - 1.0
            lines.append(f'{indent}local comp, compErr = pcall(function() return item:AddFusionComp("CG_" .. tostring(idx)) end)')
            lines.append(f'{indent}if comp then')
            lines.append(f'{indent}    print("    [OK] FusionComp created")')
            lines.append(f'{indent}    local bc = comp:AddTool("BrightnessContrast")')
            lines.append(f'{indent}    if bc then')
            lines.append(f'{indent}        bc.Brightness = {brightness}')
            lines.append(f'{indent}        bc.Contrast = {config.contrast}')
            lines.append(f'{indent}        print("    [OK] BrightnessContrast applied")')
            lines.append(f'{indent}    else')
            lines.append(f'{indent}        print("    [FAIL] BrightnessContrast tool is nil")')
            lines.append(f'{indent}    end')
            if config.saturation != 1.0:
                lines.append(f'{indent}    local cg = comp:AddTool("ColorGain")')
                lines.append(f'{indent}    if cg then cg.Saturation = {config.saturation}; print("    [OK] ColorGain applied") else print("    [FAIL] ColorGain tool is nil") end')
            lines.append(f'{indent}else')
            lines.append(f'{indent}    print("    [FAIL] FusionComp: " .. tostring(compErr))')
            lines.append(f'{indent}end')
        return "\\n".join(lines)'''

content = content[:idx] + new_func + content[end_idx:]

with open(p, 'w', encoding='utf-8') as f:
    f.write(content)

ast.parse(content)
print('Enhanced _gen_clip_color_lua with diagnostics, syntax OK')
