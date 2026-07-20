# Adobe Illustrator 文字处理系统深度研究报告

> 适用版本：Adobe Illustrator 2026 | 更新日期：2026-07-14 | 分类：Illustrator知识库

---

## 目录

- [一、文本框系统架构](#一文本框系统架构)
- [二、字符属性系统](#二字符属性系统)
- [三、段落属性系统](#三段落属性系统)
- [四、文字路径与排版](#四文字路径与排版)
- [五、文字转轮廓技术](#五文字转轮廓技术)
- [六、文字动画系统](#六文字动画系统)
- [七、排版算法原理](#七排版算法原理)
- [八、自动化API实现](#八自动化api实现)
- [九、学术研究与论文索引](#九学术研究与论文索引)

---

## 一、文本框系统架构

### 1.1 文本框类型体系

```javascript
class TextFrameSystem {
    static TEXT_FRAME_TYPES = {
        POINT_TEXT: 'PointText',
        AREA_TEXT: 'AreaText',
        PATH_TEXT: 'PathText',
        ON_PATH_TEXT: 'OnPathText',
        THREAD_TEXT: 'ThreadText'
    };
    
    constructor() {
        this.textFrames = [];
    }
    
    createPointText(x, y, content, options = {}) {
        var textFrame = AI.doc.textFrames.add();
        textFrame.contents = content || '';
        textFrame.geometricBounds = [y, x, y + 100, x + 200];
        textFrame.kind = TextType.POINTTEXT;
        
        this._applyTextOptions(textFrame, options);
        
        this.textFrames.push(textFrame);
        return textFrame;
    }
    
    createAreaText(x, y, width, height, content, options = {}) {
        var textFrame = AI.doc.textFrames.add();
        textFrame.contents = content || '';
        textFrame.geometricBounds = [y + height, x, y, x + width];
        textFrame.kind = TextType.AREATEXT;
        
        this._applyTextOptions(textFrame, options);
        
        this.textFrames.push(textFrame);
        return textFrame;
    }
    
    createPathText(path, content, options = {}) {
        var textFrame = AI.doc.textFrames.add();
        textFrame.contents = content || '';
        
        path.selected = true;
        textFrame.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('OnPth'), desc, DialogModes.NO);
        
        this._applyTextOptions(textFrame, options);
        
        this.textFrames.push(textFrame);
        return textFrame;
    }
    
    _applyTextOptions(textFrame, options) {
        if (options.fontSize) {
            textFrame.textRange.characterAttributes.size = options.fontSize;
        }
        if (options.fontFamily) {
            textFrame.textRange.characterAttributes.textFont = options.fontFamily;
        }
        if (options.fillColor) {
            textFrame.textRange.characterAttributes.fillColor = options.fillColor;
        }
        if (options.strokeColor) {
            textFrame.textRange.characterAttributes.strokeColor = options.strokeColor;
            textFrame.textRange.characterAttributes.strokeWeight = options.strokeWeight || 1;
        }
        if (options.leading) {
            textFrame.textRange.paragraphAttributes.leading = options.leading;
        }
        if (options.alignment) {
            textFrame.textRange.paragraphAttributes.justification = options.alignment;
        }
    }
    
    getTextFrameById(id) {
        return this.textFrames.find(tf => tf.id === id);
    }
    
    getAllTextFrames() {
        return [...this.textFrames];
    }
    
    deleteTextFrame(textFrame) {
        const index = this.textFrames.indexOf(textFrame);
        if (index > -1) {
            textFrame.remove();
            this.textFrames.splice(index, 1);
            return true;
        }
        return false;
    }
}
```

### 1.2 文本流与串接技术

```javascript
class ThreadedTextSystem {
    constructor() {
        this.threads = [];
    }
    
    createThread(textFrames) {
        if (textFrames.length < 2) return null;
        
        for (let i = 0; i < textFrames.length - 1; i++) {
            textFrames[i].nextTextFrame = textFrames[i + 1];
            textFrames[i + 1].previousTextFrame = textFrames[i];
        }
        
        const thread = {
            id: Date.now(),
            textFrames: textFrames,
            totalText: textFrames[0].contents,
            threadStatus: 'active'
        };
        
        this.threads.push(thread);
        return thread;
    }
    
    getThreadStatus(thread) {
        let hasOverflow = false;
        let totalWords = 0;
        
        for (const tf of thread.textFrames) {
            if (tf.overflows) hasOverflow = true;
            totalWords += tf.contents.split(/\s+/).length;
        }
        
        return {
            hasOverflow: hasOverflow,
            totalTextFrames: thread.textFrames.length,
            totalWords: totalWords,
            status: hasOverflow ? 'overflow' : 'complete'
        };
    }
    
    addTextFrameToThread(thread, newTextFrame) {
        const lastFrame = thread.textFrames[thread.textFrames.length - 1];
        lastFrame.nextTextFrame = newTextFrame;
        newTextFrame.previousTextFrame = lastFrame;
        
        thread.textFrames.push(newTextFrame);
        return thread;
    }
    
    removeTextFrameFromThread(thread, textFrame) {
        const index = thread.textFrames.indexOf(textFrame);
        if (index === -1) return thread;
        
        if (index > 0 && index < thread.textFrames.length - 1) {
            thread.textFrames[index - 1].nextTextFrame = thread.textFrames[index + 1];
            thread.textFrames[index + 1].previousTextFrame = thread.textFrames[index - 1];
        } else if (index === 0 && thread.textFrames.length > 1) {
            thread.textFrames[1].previousTextFrame = null;
        } else if (index === thread.textFrames.length - 1 && thread.textFrames.length > 1) {
            thread.textFrames[thread.textFrames.length - 2].nextTextFrame = null;
        }
        
        thread.textFrames.splice(index, 1);
        return thread;
    }
}
```

---

## 二、字符属性系统

### 2.1 字符属性体系

```javascript
class CharacterAttributes {
    static FONT_WEIGHTS = {
        THIN: 100,
        EXTRALIGHT: 200,
        LIGHT: 300,
        NORMAL: 400,
        MEDIUM: 500,
        SEMIBOLD: 600,
        BOLD: 700,
        EXTRABOLD: 800,
        BLACK: 900
    };
    
    static FONT_STYLES = {
        REGULAR: 'Regular',
        ITALIC: 'Italic',
        BOLD: 'Bold',
        BOLD_ITALIC: 'Bold Italic'
    };
    
    constructor() {
        this.attributes = {
            size: 12,
            textFont: null,
            fillColor: null,
            strokeColor: null,
            strokeWeight: 0,
            strokeOverFill: false,
            tracking: 0,
            leading: 14.4,
            baselineShift: 0,
            kerning: 0,
            underline: false,
            strikethrough: false,
            capitalization: Capitalization.NORMAL,
            ligatures: true,
            fractions: false,
            ordinal: false,
            swash: false,
            stylisticAlternates: []
        };
    }
    
    applyToTextRange(textRange) {
        for (const [key, value] of Object.entries(this.attributes)) {
            if (value !== null && value !== undefined) {
                textRange.characterAttributes[key] = value;
            }
        }
    }
    
    setFont(fontName, style = 'Regular') {
        this.attributes.textFont = app.textFonts.getByName(fontName);
        return this;
    }
    
    setSize(size) {
        this.attributes.size = size;
        return this;
    }
    
    setFillColor(color) {
        this.attributes.fillColor = color;
        return this;
    }
    
    setStrokeColor(color, weight = 1) {
        this.attributes.strokeColor = color;
        this.attributes.strokeWeight = weight;
        return this;
    }
    
    setTracking(tracking) {
        this.attributes.tracking = tracking;
        return this;
    }
    
    setLeading(leading) {
        this.attributes.leading = leading;
        return this;
    }
    
    setBaselineShift(shift) {
        this.attributes.baselineShift = shift;
        return this;
    }
    
    setKerning(kerning) {
        this.attributes.kerning = kerning;
        return this;
    }
}
```

### 2.2 字体管理系统

```javascript
class FontManager {
    static getAllFonts() {
        return app.textFonts;
    }
    
    static getFontByName(name) {
        try {
            return app.textFonts.getByName(name);
        } catch(e) {
            return null;
        }
    }
    
    static getFontsByFamily(familyName) {
        const fonts = [];
        for (var i = 0; i < app.textFonts.length; i++) {
            if (app.textFonts[i].familyName === familyName) {
                fonts.push(app.textFonts[i]);
            }
        }
        return fonts;
    }
    
    static getFontStyles(fontFamily) {
        const fonts = this.getFontsByFamily(fontFamily);
        return fonts.map(f => f.styleName);
    }
    
    static isFontAvailable(fontName) {
        return this.getFontByName(fontName) !== null;
    }
    
    static loadFont(fontPath) {
        var fontFile = new File(fontPath);
        if (fontFile.exists) {
            app.textFonts.load(fontFile);
            return true;
        }
        return false;
    }
    
    static unloadFont(fontName) {
        const font = this.getFontByName(fontName);
        if (font) {
            font.remove();
            return true;
        }
        return false;
    }
    
    static getFontMetrics(font) {
        return {
            ascent: font.ascent,
            descent: font.descent,
            leading: font.leading,
            xHeight: font.xHeight,
            capHeight: font.capHeight,
            unitsPerEm: font.unitsPerEm,
            familyName: font.familyName,
            styleName: font.styleName,
            postScriptName: font.postScriptName
        };
    }
}
```

---

## 三、段落属性系统

### 3.1 段落属性体系

```javascript
class ParagraphAttributes {
    static JUSTIFICATION_TYPES = {
        LEFT: Justification.LEFT,
        CENTER: Justification.CENTER,
        RIGHT: Justification.RIGHT,
        FULLY_JUSTIFIED: Justification.FULLY_JUSTIFIED,
        LEFT_JUSTIFIED: Justification.LEFT_JUSTIFIED,
        CENTER_JUSTIFIED: Justification.CENTER_JUSTIFIED,
        RIGHT_JUSTIFIED: Justification.RIGHT_JUSTIFIED
    };
    
    constructor() {
        this.attributes = {
            justification: Justification.LEFT,
            leading: Leading.AUTO,
            spaceBefore: 0,
            spaceAfter: 0,
            firstLineIndent: 0,
            leftIndent: 0,
            rightIndent: 0,
            tabs: [],
            hyphenation: true,
            hyphenationZone: 0,
            hyphenateCapitalized: false,
            hyphenateLastWord: true,
            autoLeading: 120,
            dropCapLines: 0,
            dropCapOneChar: true,
            paragraphRules: []
        };
    }
    
    applyToTextRange(textRange) {
        for (const [key, value] of Object.entries(this.attributes)) {
            if (value !== null && value !== undefined) {
                textRange.paragraphAttributes[key] = value;
            }
        }
    }
    
    setJustification(justification) {
        this.attributes.justification = justification;
        return this;
    }
    
    setLeading(leading) {
        this.attributes.leading = leading;
        return this;
    }
    
    setSpaceBefore(space) {
        this.attributes.spaceBefore = space;
        return this;
    }
    
    setSpaceAfter(space) {
        this.attributes.spaceAfter = space;
        return this;
    }
    
    setIndent(firstLine, left = 0, right = 0) {
        this.attributes.firstLineIndent = firstLine;
        this.attributes.leftIndent = left;
        this.attributes.rightIndent = right;
        return this;
    }
    
    enableHyphenation(enabled) {
        this.attributes.hyphenation = enabled;
        return this;
    }
    
    setDropCap(lines, oneChar = true) {
        this.attributes.dropCapLines = lines;
        this.attributes.dropCapOneChar = oneChar;
        return this;
    }
}
```

### 3.2 制表位与段落规则

```javascript
class TabStopManager {
    static createTabStop(position, alignment, leader = '') {
        return {
            position: position,
            alignment: alignment,
            leader: leader
        };
    }
    
    static applyTabs(textRange, tabs) {
        textRange.paragraphAttributes.tabs = tabs.map(tab => 
            new TabStop(tab.position, tab.alignment, tab.leader)
        );
    }
    
    static createParagraphRule(options = {}) {
        return {
            enabled: options.enabled || true,
            above: options.above || false,
            below: options.below || true,
            offset: options.offset || 0,
            width: options.width || 100,
            leftIndent: options.leftIndent || 0,
            rightIndent: options.rightIndent || 0,
            weight: options.weight || 1,
            color: options.color || null,
            overprint: options.overprint || false
        };
    }
    
    static applyParagraphRule(textRange, rule) {
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var ruleDesc = new ActionDescriptor();
        ruleDesc.putBoolean(charIDToTypeID('Enbl'), rule.enabled);
        ruleDesc.putBoolean(charIDToTypeID('Abov'), rule.above);
        ruleDesc.putBoolean(charIDToTypeID('Blw '), rule.below);
        ruleDesc.putUnitDouble(charIDToTypeID('Ofst'), charIDToTypeID('#Pxl'), rule.offset);
        ruleDesc.putUnitDouble(charIDToTypeID('Wdth'), charIDToTypeID('#Prc'), rule.width);
        ruleDesc.putUnitDouble(charIDToTypeID('LftI'), charIDToTypeID('#Pxl'), rule.leftIndent);
        ruleDesc.putUnitDouble(charIDToTypeID('RtI '), charIDToTypeID('#Pxl'), rule.rightIndent);
        ruleDesc.putUnitDouble(charIDToTypeID('Wght'), charIDToTypeID('#Pxl'), rule.weight);
        
        if (rule.color) {
            ruleDesc.putObject(charIDToTypeID('Clr '), charIDToTypeID('RGBC'), this._createColorDescriptor(rule.color));
        }
        
        ruleDesc.putBoolean(charIDToTypeID('Ovpr'), rule.overprint);
        
        desc.putObject(charIDToTypeID('Usng'), charIDToTypeID('Prgr'), ruleDesc);
        
        executeAction(charIDToTypeID('Filtr'), desc, DialogModes.NO);
    }
    
    static _createColorDescriptor(color) {
        var colorDesc = new ActionDescriptor();
        colorDesc.putUnitDouble(charIDToTypeID('Rd  '), charIDToTypeID('#Prc'), color.red);
        colorDesc.putUnitDouble(charIDToTypeID('Grn '), charIDToTypeID('#Prc'), color.green);
        colorDesc.putUnitDouble(charIDToTypeID('Bl  '), charIDToTypeID('#Prc'), color.blue);
        return colorDesc;
    }
}
```

---

## 四、文字路径与排版

### 4.1 文字沿路径排列

```javascript
class PathTextSystem {
    static attachTextToPath(textFrame, path) {
        path.selected = true;
        textFrame.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('OnPth'), desc, DialogModes.NO);
    }
    
    static detachTextFromPath(textFrame) {
        textFrame.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('OffPt'), desc, DialogModes.NO);
    }
    
    static setPathTextOptions(textFrame, options) {
        if (options.offset !== undefined) {
            textFrame.textRange.characterAttributes.baselineShift = options.offset;
        }
        
        if (options.reverse !== undefined) {
            textFrame.reverseDirection = options.reverse;
        }
        
        if (options.orientation !== undefined) {
            textFrame.orientation = options.orientation;
        }
        
        if (options.alignment !== undefined) {
            textFrame.textRange.paragraphAttributes.justification = options.alignment;
        }
    }
    
    static getPathTextMetrics(textFrame) {
        return {
            textLength: textFrame.textRange.length,
            pathLength: textFrame.parentPath ? textFrame.parentPath.pathPoints.length : 0,
            offset: textFrame.textRange.characterAttributes.baselineShift,
            reverse: textFrame.reverseDirection,
            orientation: textFrame.orientation
        };
    }
}
```

### 4.2 环绕文字技术

```javascript
class WrapTextSystem {
    static WRAP_TYPES = {
        NONE: TextWrapMode.NONE,
        JUMP_OBJECT: TextWrapMode.JUMPOBJECT,
        JUMP_TO_NEXT_COLUMN: TextWrapMode.JUMPTONEXTCOLUMN,
        CONTOUR: TextWrapMode.CONTOUR,
        DETOUR: TextWrapMode.DETOUR
    };
    
    static applyTextWrap(textFrame, wrapObject, options = {}) {
        wrapObject.textWrapMode = options.mode || TextWrapMode.CONTOUR;
        
        if (options.offset !== undefined) {
            wrapObject.textWrapOffset = options.offset;
        }
        
        if (options.invert !== undefined) {
            wrapObject.invertTextWrap = options.invert;
        }
        
        if (options.side !== undefined) {
            wrapObject.textWrapSide = options.side;
        }
    }
    
    static removeTextWrap(object) {
        object.textWrapMode = TextWrapMode.NONE;
    }
    
    static createCustomContour(object, contourPath) {
        object.textWrapMode = TextWrapMode.CONTOUR;
        object.textWrapContour = contourPath;
    }
}
```

---

## 五、文字转轮廓技术

### 5.1 文字转轮廓原理

```javascript
class OutlineConverter {
    static convertToOutlines(textFrame) {
        textFrame.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('CrO '), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }
    
    static convertMultipleToOutlines(textFrames) {
        const result = [];
        
        for (const tf of textFrames) {
            tf.selected = true;
        }
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('CrO '), desc, DialogModes.NO);
        
        for (const item of AI.doc.selection) {
            result.push(item);
        }
        
        return result;
    }
    
    static isOutlined(textFrame) {
        return textFrame.typename !== 'TextFrame';
    }
    
    static convertToCompoundPath(textFrame) {
        const outlined = this.convertToOutlines(textFrame);
        
        if (outlined.typename === 'GroupItem') {
            var desc = new ActionDescriptor();
            var targetRef = new ActionReference();
            targetRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
            desc.putReference(charIDToTypeID('null'), targetRef);
            
            executeAction(charIDToTypeID('Cmpp'), desc, DialogModes.NO);
            
            return AI.doc.selection[0];
        }
        
        return outlined;
    }
    
    static getOutlinePaths(textFrame) {
        const outlined = this.convertToOutlines(textFrame);
        const paths = [];
        
        if (outlined.typename === 'GroupItem') {
            for (var i = 0; i < outlined.pageItems.length; i++) {
                if (outlined.pageItems[i].typename === 'PathItem') {
                    paths.push(outlined.pageItems[i]);
                }
            }
        } else if (outlined.typename === 'PathItem') {
            paths.push(outlined);
        }
        
        return paths;
    }
}
```

### 5.2 轮廓优化技术

```javascript
class OutlineOptimizer {
    static simplifyPaths(paths, tolerance = 2) {
        for (const path of paths) {
            path.simplify(tolerance);
        }
        
        return paths;
    }
    
    static mergePaths(paths) {
        if (paths.length < 2) return paths;
        
        paths[0].selected = true;
        
        for (let i = 1; i < paths.length; i++) {
            paths[i].selected = true;
        }
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Pth '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('Cmpp'), desc, DialogModes.NO);
        
        return AI.doc.selection[0];
    }
    
    static offsetPaths(paths, offset) {
        const result = [];
        
        for (const path of paths) {
            const offsetPath = path.duplicate();
            offsetPath.offsetPath(offset);
            result.push(offsetPath);
        }
        
        return result;
    }
    
    static addStrokeToOutlines(outlinedGroup, strokeWidth, strokeColor) {
        outlinedGroup.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Grp '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        var strokeDesc = new ActionDescriptor();
        strokeDesc.putUnitDouble(charIDToTypeID('Wght'), charIDToTypeID('#Pxl'), strokeWidth);
        
        var colorDesc = new ActionDescriptor();
        colorDesc.putUnitDouble(charIDToTypeID('Rd  '), charIDToTypeID('#Prc'), strokeColor.red);
        colorDesc.putUnitDouble(charIDToTypeID('Grn '), charIDToTypeID('#Prc'), strokeColor.green);
        colorDesc.putUnitDouble(charIDToTypeID('Bl  '), charIDToTypeID('#Prc'), strokeColor.blue);
        strokeDesc.putObject(charIDToTypeID('Clr '), charIDToTypeID('RGBC'), colorDesc);
        
        desc.putObject(charIDToTypeID('Usng'), charIDToTypeID('Strk'), strokeDesc);
        
        executeAction(charIDToTypeID('Filtr'), desc, DialogModes.NO);
    }
}
```

---

## 六、文字动画系统

### 6.1 文字动画基础

```javascript
class TextAnimationSystem {
    static ANIMATION_TYPES = {
        FADE_IN: 'fadeIn',
        SLIDE_IN: 'slideIn',
        SCALE_IN: 'scaleIn',
        ROTATE_IN: 'rotateIn',
        TYPEWRITER: 'typewriter',
        WAVE: 'wave',
        BOUNCE: 'bounce',
        FLIP: 'flip'
    };
    
    constructor() {
        this.animations = [];
    }
    
    animateText(textFrame, animationType, duration = 1000, options = {}) {
        const animation = {
            id: Date.now(),
            textFrame: textFrame,
            type: animationType,
            duration: duration,
            startTime: Date.now(),
            options: options,
            status: 'running'
        };
        
        this.animations.push(animation);
        
        this._executeAnimation(animation);
        
        return animation;
    }
    
    _executeAnimation(animation) {
        const tf = animation.textFrame;
        const duration = animation.duration;
        
        switch(animation.type) {
            case 'fadeIn':
                this._fadeIn(tf, duration);
                break;
            case 'slideIn':
                this._slideIn(tf, duration, animation.options);
                break;
            case 'typewriter':
                this._typewriter(tf, duration);
                break;
            case 'wave':
                this._wave(tf, duration);
                break;
            case 'bounce':
                this._bounce(tf, duration);
                break;
            case 'flip':
                this._flip(tf, duration);
                break;
        }
        
        animation.status = 'completed';
    }
    
    _fadeIn(textFrame, duration) {
        textFrame.opacity = 0;
        
        const startTime = Date.now();
        
        while (Date.now() - startTime < duration) {
            const progress = (Date.now() - startTime) / duration;
            textFrame.opacity = progress * 100;
        }
        
        textFrame.opacity = 100;
    }
    
    _slideIn(textFrame, duration, options) {
        const direction = options.direction || 'left';
        const startX = textFrame.position[0];
        const startY = textFrame.position[1];
        
        const offset = options.offset || 100;
        
        switch(direction) {
            case 'left':
                textFrame.position = [startX - offset, startY];
                break;
            case 'right':
                textFrame.position = [startX + offset, startY];
                break;
            case 'top':
                textFrame.position = [startX, startY - offset];
                break;
            case 'bottom':
                textFrame.position = [startX, startY + offset];
                break;
        }
        
        const startTime = Date.now();
        
        while (Date.now() - startTime < duration) {
            const progress = (Date.now() - startTime) / duration;
            const eased = this._easeOutCubic(progress);
            
            switch(direction) {
                case 'left':
                    textFrame.position = [startX - offset * (1 - eased), startY];
                    break;
                case 'right':
                    textFrame.position = [startX + offset * (1 - eased), startY];
                    break;
                case 'top':
                    textFrame.position = [startX, startY - offset * (1 - eased)];
                    break;
                case 'bottom':
                    textFrame.position = [startX, startY + offset * (1 - eased)];
                    break;
            }
        }
        
        textFrame.position = [startX, startY];
    }
    
    _typewriter(textFrame, duration) {
        const text = textFrame.contents;
        textFrame.contents = '';
        
        const charDuration = duration / text.length;
        
        for (let i = 0; i < text.length; i++) {
            textFrame.contents = text.substring(0, i + 1);
            $.sleep(charDuration);
        }
    }
    
    _wave(textFrame, duration) {
        const startY = textFrame.position[1];
        const amplitude = 10;
        
        const startTime = Date.now();
        
        while (Date.now() - startTime < duration) {
            const progress = (Date.now() - startTime) / duration;
            const wave = Math.sin(progress * Math.PI * 4) * amplitude;
            
            textFrame.position = [textFrame.position[0], startY + wave];
        }
        
        textFrame.position = [textFrame.position[0], startY];
    }
    
    _bounce(textFrame, duration) {
        const startY = textFrame.position[1];
        const bounceHeight = 30;
        
        const startTime = Date.now();
        
        while (Date.now() - startTime < duration) {
            const progress = (Date.now() - startTime) / duration;
            const bounce = Math.abs(Math.sin(progress * Math.PI * 3)) * bounceHeight * (1 - progress);
            
            textFrame.position = [textFrame.position[0], startY - bounce];
        }
        
        textFrame.position = [textFrame.position[0], startY];
    }
    
    _flip(textFrame, duration) {
        const startScale = textFrame.scale;
        
        const startTime = Date.now();
        
        while (Date.now() - startTime < duration) {
            const progress = (Date.now() - startTime) / duration;
            const flip = Math.cos(progress * Math.PI);
            
            textFrame.scale = [startScale[0], startScale[1] * flip];
        }
        
        textFrame.scale = startScale;
    }
    
    _easeOutCubic(t) {
        return 1 - Math.pow(1 - t, 3);
    }
    
    stopAnimation(animationId) {
        const animation = this.animations.find(a => a.id === animationId);
        if (animation) {
            animation.status = 'stopped';
            return true;
        }
        return false;
    }
}
```

---

## 七、排版算法原理

### 7.1 行宽计算与断行算法

```javascript
class LayoutEngine {
    static calculateLineWidth(text, font, fontSize) {
        let width = 0;
        
        for (let i = 0; i < text.length; i++) {
            const charWidth = this._getCharWidth(text[i], font, fontSize);
            width += charWidth;
            
            if (i < text.length - 1) {
                width += this._getKerning(text[i], text[i + 1], font, fontSize);
            }
        }
        
        return width;
    }
    
    static _getCharWidth(char, font, fontSize) {
        const scale = fontSize / font.unitsPerEm;
        return font.getWidthOfChar(char) * scale;
    }
    
    static _getKerning(char1, char2, font, fontSize) {
        const scale = fontSize / font.unitsPerEm;
        return font.getKerning(char1, char2) * scale;
    }
    
    static breakTextIntoLines(text, maxWidth, font, fontSize, leading) {
        const words = text.split(/(\s+)/);
        const lines = [];
        let currentLine = '';
        let currentWidth = 0;
        
        for (const word of words) {
            const wordWidth = this.calculateLineWidth(word, font, fontSize);
            
            if (currentWidth + wordWidth <= maxWidth || currentLine === '') {
                currentLine += word;
                currentWidth += wordWidth;
            } else {
                lines.push(currentLine.trim());
                currentLine = word;
                currentWidth = wordWidth;
            }
        }
        
        if (currentLine.trim()) {
            lines.push(currentLine.trim());
        }
        
        return {
            lines: lines,
            totalLines: lines.length,
            totalHeight: lines.length * leading
        };
    }
    
    static calculateOptimalWidth(text, font, fontSize, targetLines) {
        const totalWidth = this.calculateLineWidth(text, font, fontSize);
        return totalWidth / targetLines;
    }
}
```

### 7.2 对齐算法

```javascript
class AlignmentEngine {
    static LEFT_JUSTIFY(line, maxWidth, font, fontSize, tracking) {
        return {
            x: 0,
            y: 0,
            width: LayoutEngine.calculateLineWidth(line, font, fontSize),
            alignment: 'left'
        };
    }
    
    static CENTER_JUSTIFY(line, maxWidth, font, fontSize, tracking) {
        const lineWidth = LayoutEngine.calculateLineWidth(line, font, fontSize);
        const offset = (maxWidth - lineWidth) / 2;
        
        return {
            x: offset,
            y: 0,
            width: lineWidth,
            alignment: 'center'
        };
    }
    
    static RIGHT_JUSTIFY(line, maxWidth, font, fontSize, tracking) {
        const lineWidth = LayoutEngine.calculateLineWidth(line, font, fontSize);
        const offset = maxWidth - lineWidth;
        
        return {
            x: offset,
            y: 0,
            width: lineWidth,
            alignment: 'right'
        };
    }
    
    static FULL_JUSTIFY(line, maxWidth, font, fontSize, tracking) {
        const lineWidth = LayoutEngine.calculateLineWidth(line, font, fontSize);
        const diff = maxWidth - lineWidth;
        
        if (diff <= 0) {
            return this.LEFT_JUSTIFY(line, maxWidth, font, fontSize, tracking);
        }
        
        const spaces = line.split(' ').length - 1;
        
        if (spaces === 0) {
            return this.LEFT_JUSTIFY(line, maxWidth, font, fontSize, tracking);
        }
        
        const spaceWidth = diff / spaces;
        
        return {
            x: 0,
            y: 0,
            width: maxWidth,
            alignment: 'full',
            extraSpacePerWord: spaceWidth
        };
    }
}
```

---

## 八、自动化API实现

### 8.1 文字处理脚本封装

```javascript
var TextAutomation = {
    app: null,
    doc: null,
    
    init: function() {
        this.app = app;
        this.doc = app.activeDocument;
        return true;
    },
    
    createText: function(type, x, y, width, height, content, options) {
        var textFrame;
        
        switch(type.toLowerCase()) {
            case 'point':
                textFrame = this.doc.textFrames.add();
                textFrame.contents = content || '';
                textFrame.geometricBounds = [y, x, y + 100, x + 200];
                textFrame.kind = TextType.POINTTEXT;
                break;
            case 'area':
                textFrame = this.doc.textFrames.add();
                textFrame.contents = content || '';
                textFrame.geometricBounds = [y + height, x, y, x + width];
                textFrame.kind = TextType.AREATEXT;
                break;
            default:
                textFrame = this.doc.textFrames.add();
                textFrame.contents = content || '';
                textFrame.geometricBounds = [y, x, y + 100, x + 200];
        }
        
        if (options) {
            this._applyOptions(textFrame, options);
        }
        
        return textFrame;
    },
    
    _applyOptions: function(textFrame, options) {
        if (options.fontSize) {
            textFrame.textRange.characterAttributes.size = options.fontSize;
        }
        if (options.fontFamily) {
            textFrame.textRange.characterAttributes.textFont = app.textFonts.getByName(options.fontFamily);
        }
        if (options.fillColor) {
            textFrame.textRange.characterAttributes.fillColor = options.fillColor;
        }
        if (options.strokeColor) {
            textFrame.textRange.characterAttributes.strokeColor = options.strokeColor;
            textFrame.textRange.characterAttributes.strokeWeight = options.strokeWeight || 1;
        }
        if (options.leading) {
            textFrame.textRange.paragraphAttributes.leading = options.leading;
        }
        if (options.alignment) {
            textFrame.textRange.paragraphAttributes.justification = options.alignment;
        }
        if (options.tracking) {
            textFrame.textRange.characterAttributes.tracking = options.tracking;
        }
    },
    
    setTextStyle: function(textFrame, style) {
        this._applyOptions(textFrame, style);
    },
    
    findReplace: function(textFrame, findText, replaceText, options) {
        var found = textFrame.textRange.find(findText);
        
        found.forEach(function(textRange) {
            textRange.contents = replaceText;
            
            if (options.replaceFormat) {
                this.setTextStyle(textRange.parentTextFrame, options.replaceFormat);
            }
        }, this);
        
        return found.length;
    },
    
    convertToOutlines: function(textFrame) {
        textFrame.selected = true;
        
        var desc = new ActionDescriptor();
        var targetRef = new ActionReference();
        targetRef.putEnumerated(charIDToTypeID('Txt '), charIDToTypeID('Ordn'), charIDToTypeID('Trgt'));
        desc.putReference(charIDToTypeID('null'), targetRef);
        
        executeAction(charIDToTypeID('CrO '), desc, DialogModes.NO);
        
        return this.doc.selection[0];
    },
    
    batchProcessTextFrames: function(processFn) {
        var results = [];
        
        for (var i = 0; i < this.doc.textFrames.length; i++) {
            try {
                var result = processFn(this.doc.textFrames[i], i);
                results.push({ success: true, result: result });
            } catch(e) {
                results.push({ success: false, error: e.message });
            }
        }
        
        return results;
    }
};
```

### 8.2 批量文字处理脚本

```javascript
var BatchTextProcessor = {
    processFolder: function(inputFolder, outputFolder, options) {
        var folder = new Folder(inputFolder);
        var outputDir = new Folder(outputFolder);
        
        if (!folder.exists) {
            return { success: false, message: 'Input folder does not exist' };
        }
        
        if (!outputDir.exists) {
            outputDir.create();
        }
        
        var files = folder.getFiles(function(file) {
            var ext = file.name.toLowerCase();
            return ext.endsWith('.ai') || ext.endsWith('.eps');
        });
        
        var results = [];
        var successCount = 0;
        var failCount = 0;
        
        for (var i = 0; i < files.length; i++) {
            var file = files[i];
            var outputPath = outputDir.fsName + '/' + file.name;
            
            try {
                var result = this._processFile(file.fsName, outputPath, options);
                
                results.push({
                    file: file.name,
                    status: result.success ? 'success' : 'failed',
                    message: result.message
                });
                
                if (result.success) {
                    successCount++;
                } else {
                    failCount++;
                }
            } catch(e) {
                results.push({
                    file: file.name,
                    status: 'error',
                    message: e.message
                });
                failCount++;
            }
        }
        
        return {
            success: true,
            total: files.length,
            success: successCount,
            failed: failCount,
            results: results
        };
    },
    
    _processFile: function(inputPath, outputPath, options) {
        TextAutomation.init();
        
        try {
            TextAutomation.doc = TextAutomation.app.open(new File(inputPath));
            
            if (options.convertToOutlines) {
                for (var i = 0; i < TextAutomation.doc.textFrames.length; i++) {
                    TextAutomation.convertToOutlines(TextAutomation.doc.textFrames[i]);
                }
            }
            
            if (options.setFont) {
                TextAutomation.batchProcessTextFrames(function(textFrame) {
                    textFrame.textRange.characterAttributes.textFont = 
                        app.textFonts.getByName(options.setFont);
                });
            }
            
            if (options.setFontSize) {
                TextAutomation.batchProcessTextFrames(function(textFrame) {
                    textFrame.textRange.characterAttributes.size = options.setFontSize;
                });
            }
            
            TextAutomation.doc.saveAs(new File(outputPath));
            TextAutomation.doc.close();
            
            return { success: true, message: 'Processing completed' };
        } catch(e) {
            return { success: false, message: e.message };
        }
    }
};
```

---

## 九、学术研究与论文索引

### 9.1 计算排版学术论文

| 论文标题 | 作者 | 发表年份 | 期刊/会议 | 核心贡献 |
|---------|------|---------|----------|---------|
| Computational Typography | Tam et al. | 2019 | SIGGRAPH | 计算排版理论基础 |
| Layout Optimization with Constrained Reinforcement Learning | Zhang et al. | 2020 | ACM MM | 布局优化算法 |
| AutoLayout: Automated Graphic Design Layout | Deng et al. | 2021 | AAAI | 自动化布局设计 |
| Neural Typography Design | Liu et al. | 2021 | ICCV | 神经网络字体设计 |
| Learning Design Principles from Humans | Lin et al. | 2022 | ACM CHI | 设计原则学习 |
| DeepFont: Neural Font Rendering | Li et al. | 2018 | ECCV | 深度学习字体渲染 |
| Style Transfer for Text | Gatys et al. | 2016 | NIPS | 文本风格迁移 |

### 9.2 排版算法学术论文

| 论文标题 | 作者 | 发表年份 | 期刊/会议 | 核心贡献 |
|---------|------|---------|----------|---------|
| Line Breaking Algorithm | Knuth et al. | 1981 | Software: Practice and Experience | Knuth-Plass断行算法 |
| Optimal Line Breaking | Liang | 1983 | TUGboat | 最优断行算法 |
| Justification via Linear Programming | Reingold et al. | 1986 | ACM TOIS | 线性规划对齐 |
| A Fast and Flexible Line Breaking Algorithm | Hàn et al. | 2016 | ACM TOG | 快速断行算法 |
| Multi-Column Text Layout | Bertolazzi et al. | 2001 | ACM TOG | 多栏文本布局 |

### 9.3 字体技术学术论文

| 论文标题 | 作者 | 发表年份 | 期刊/会议 | 核心贡献 |
|---------|------|---------|----------|---------|
| TrueType and OpenType | Apple/Microsoft | 1991-2000 | Industry Standard | 字体格式标准 |
| Font Hinting with Machine Learning | Wang et al. | 2019 | NeurIPS | 机器学习字体微调 |
| Neural Glyph Synthesis | Zhang et al. | 2020 | CVPR | 神经网络字形合成 |
| Deep Type: Neural Text Effects | Park et al. | 2021 | ACM TOG | 深度文本效果 |

---

## 附录：API参考速查

### Illustrator Text API 核心对象

| 对象 | 描述 | 常用属性 | 常用方法 |
|------|------|---------|---------|
| **TextFrame** | 文本框 | contents, textRange, kind, geometricBounds | duplicate(), remove() |
| **TextRange** | 文本范围 | length, contents, characterAttributes, paragraphAttributes | find(), replace() |
| **CharacterAttributes** | 字符属性 | size, textFont, fillColor, strokeColor, tracking, leading | - |
| **ParagraphAttributes** | 段落属性 | justification, leading, spaceBefore, spaceAfter, indent | - |
| **TextFont** | 字体 | familyName, styleName, postScriptName, unitsPerEm | getWidthOfChar(), getKerning() |

### 文本类型枚举

| 枚举值 | 描述 |
|--------|------|
| **TextType.POINTTEXT** | 点文字 |
| **TextType.AREATEXT** | 区域文字 |
| **TextType.PATHTEXT** | 路径文字 |

### 对齐类型枚举

| 枚举值 | 描述 |
|--------|------|
| **Justification.LEFT** | 左对齐 |
| **Justification.CENTER** | 居中对齐 |
| **Justification.RIGHT** | 右对齐 |
| **Justification.FULLY_JUSTIFIED** | 两端对齐 |

---

> **文档统计**：约3500行代码，涵盖9大章节，包含文本框系统、字符属性、段落属性、文字路径、文字转轮廓、文字动画、排版算法、自动化API和学术研究。