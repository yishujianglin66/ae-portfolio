(function(){var _r={};try{
var proj=app.project;
var existing=null;
for(var _i=1;_i<=proj.numItems;_i++){if(proj.item(_i).name==="V17_Font_Edition"){existing=proj.item(_i);break;}}
if(existing){existing.remove();}
var comp=proj.items.addComp("V17_Font_Edition",1080,1920,1,23.15,30);
comp.bgColor=[0.02,0.02,0.05];
_r.compName=comp.name;_r.width=1080;_r.height=1920;_r.duration=23.15;
// === Intro :: intro_hero :: VINLAND SAGA ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("VINLAND SAGA");
tl.name="TXT_hero_cn_brutal";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZLanTingHeiS-ExtraBold";
td.fontSize=88;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=0.3;tl.inPoint=0.3;tl.outPoint=3.8;
tl.position.setValueAtTime(0.3,[540.0,178.6]);
tl.position.setValueAtTime(0.3+0.4,[540.0,153.6]);
tl.scale.setValueAtTime(0.3,[0,0]);
tl.opacity.setValueAtTime(0.3,0);
tl.scale.setValueAtTime(0.42,[108,108]);
tl.opacity.setValueAtTime(0.42,100);
tl.scale.setValueAtTime(0.65,[98,98]);
tl.opacity.setValueAtTime(0.65,100);
tl.scale.setValueAtTime(0.8,[100,100]);
tl.opacity.setValueAtTime(0.8,100);
tl.opacity.setValueAtTime(0.3,0);
tl.opacity.setValueAtTime(0.3+0.2,100);
tl.opacity.setValueAtTime(3.8-0.2,100);
tl.opacity.setValueAtTime(3.8,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZLanTingHeiS-ExtraBold',text:'VINLAND SAGA',start:0.3,end:3.8};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Intro :: intro_hero :: 冰 海 战 记 ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("冰 海 战 记");
tl.name="TXT_hero_cn_brutal";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZLanTingHeiS-ExtraBold";
td.fontSize=56;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=1.0;tl.inPoint=1.0;tl.outPoint=3.8;
tl.position.setValueAtTime(1.0,[540.0,370.59999999999997]);
tl.position.setValueAtTime(1.0+0.4,[540.0,345.59999999999997]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(1.0,0);
tl.opacity.setValueAtTime(1.0+0.2,100);
tl.opacity.setValueAtTime(3.8-0.2,100);
tl.opacity.setValueAtTime(3.8,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZLanTingHeiS-ExtraBold',text:'冰 海 战 记',start:1.0,end:3.8};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Intro :: intro_credit :: —— 战士的史诗 —— ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("—— 战士的史诗 ——");
tl.name="TXT_credit_cn_puhui";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="AlibabaPuHuiTi-3-45-Light";
td.fontSize=30;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=0.2;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=2.0;tl.inPoint=2.0;tl.outPoint=3.6;
tl.position.setValueAtTime(2.0,[540.0,485.79999999999995]);
tl.position.setValueAtTime(2.0+0.4,[540.0,460.79999999999995]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(2.0,0);
tl.opacity.setValueAtTime(2.0+0.2,100);
tl.opacity.setValueAtTime(3.6-0.2,100);
tl.opacity.setValueAtTime(3.6,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'AlibabaPuHuiTi-3-45-Light',text:'—— 战士的史诗 ——',start:2.0,end:3.6};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Build :: build_action :: 当战争的火焰再次燃起 ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("当战争的火焰再次燃起");
tl.name="TXT_sub_cn_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZJingHeiS-R-GB";
td.fontSize=36;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[1.000,0.133,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=5.0;tl.inPoint=5.0;tl.outPoint=7.5;
tl.position.setValueAtTime(5.0,[540.0,1657.0]);
tl.position.setValueAtTime(5.0+0.4,[540.0,1632.0]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(5.0,0);
tl.opacity.setValueAtTime(5.0+0.2,100);
tl.opacity.setValueAtTime(7.5-0.2,100);
tl.opacity.setValueAtTime(7.5,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZJingHeiS-R-GB',text:'当战争的火焰再次燃起',start:5.0,end:7.5};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Build :: build_action :: THE SAGA CONTINUES ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("THE SAGA CONTINUES");
tl.name="TXT_sub_cn_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZJingHeiS-R-GB";
td.fontSize=26;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[1.000,0.133,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=7.5;tl.inPoint=7.5;tl.outPoint=9.0;
tl.position.setValueAtTime(7.5,[540.0,1714.6]);
tl.position.setValueAtTime(7.5+0.4,[540.0,1689.6]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(7.5,0);
tl.opacity.setValueAtTime(7.5+0.2,100);
tl.opacity.setValueAtTime(9.0-0.2,100);
tl.opacity.setValueAtTime(9.0,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZJingHeiS-R-GB',text:'THE SAGA CONTINUES',start:7.5,end:9.0};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Drop :: drop_battle_en :: BATTLE ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("BATTLE");
tl.name="TXT_sub_en_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="Impact";
td.fontSize=110;
td.applyFill=true;td.fillColor=[1.000,0.933,0.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=2.5;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=9.0;tl.inPoint=9.0;tl.outPoint=10.8;
tl.position.setValueAtTime(9.0,[540.0,1561.0]);
tl.position.setValueAtTime(9.0+0.4,[540.0,1536.0]);
tl.scale.setValueAtTime(9.0,[200,200]);
tl.opacity.setValueAtTime(9.0,0);
tl.rotation.setValueAtTime(9.0,-8);
tl.scale.setValueAtTime(9.18,[100,100]);
tl.opacity.setValueAtTime(9.18,100);
tl.scale.setValueAtTime(9.3,[108,108]);
tl.opacity.setValueAtTime(9.3,100);
tl.scale.setValueAtTime(9.4,[100,100]);
tl.opacity.setValueAtTime(9.4,100);
tl.opacity.setValueAtTime(9.0,0);
tl.opacity.setValueAtTime(9.0+0.2,100);
tl.opacity.setValueAtTime(10.8-0.2,100);
tl.opacity.setValueAtTime(10.8,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'Impact',text:'BATTLE',start:9.0,end:10.8};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Drop :: drop_battle_en :: VS ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("VS");
tl.name="TXT_sub_en_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="Impact";
td.fontSize=140;
td.applyFill=true;td.fillColor=[1.000,0.933,0.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=2.5;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=11.5;tl.inPoint=11.5;tl.outPoint=12.5;
tl.position.setValueAtTime(11.5,[540.0,985.0]);
tl.position.setValueAtTime(11.5+0.4,[540.0,960.0]);
tl.scale.setValueAtTime(11.5,[200,200]);
tl.opacity.setValueAtTime(11.5,0);
tl.rotation.setValueAtTime(11.5,-8);
tl.scale.setValueAtTime(11.68,[100,100]);
tl.opacity.setValueAtTime(11.68,100);
tl.scale.setValueAtTime(11.8,[108,108]);
tl.opacity.setValueAtTime(11.8,100);
tl.scale.setValueAtTime(11.9,[100,100]);
tl.opacity.setValueAtTime(11.9,100);
tl.opacity.setValueAtTime(11.5,0);
tl.opacity.setValueAtTime(11.5+0.2,100);
tl.opacity.setValueAtTime(12.5-0.2,100);
tl.opacity.setValueAtTime(12.5,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'Impact',text:'VS',start:11.5,end:12.5};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Drop :: drop_battle_en :: REDEMPTION ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("REDEMPTION");
tl.name="TXT_sub_en_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="Impact";
td.fontSize=80;
td.applyFill=true;td.fillColor=[1.000,0.933,0.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=2.5;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=13.0;tl.inPoint=13.0;tl.outPoint=14.8;
tl.position.setValueAtTime(13.0,[540.0,409.0]);
tl.position.setValueAtTime(13.0+0.4,[540.0,384.0]);
tl.scale.setValueAtTime(13.0,[0,0]);
tl.opacity.setValueAtTime(13.0,0);
tl.scale.setValueAtTime(13.12,[108,108]);
tl.opacity.setValueAtTime(13.12,100);
tl.scale.setValueAtTime(13.35,[98,98]);
tl.opacity.setValueAtTime(13.35,100);
tl.scale.setValueAtTime(13.5,[100,100]);
tl.opacity.setValueAtTime(13.5,100);
tl.opacity.setValueAtTime(13.0,0);
tl.opacity.setValueAtTime(13.0+0.2,100);
tl.opacity.setValueAtTime(14.8-0.2,100);
tl.opacity.setValueAtTime(14.8,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'Impact',text:'REDEMPTION',start:13.0,end:14.8};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Drop :: drop_battle_cn :: 战 ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("战");
tl.name="TXT_sub_cn_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZJingHeiS-R-GB";
td.fontSize=130;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[1.000,0.133,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=9.3;tl.inPoint=9.3;tl.outPoint=9.7;
tl.position.setValueAtTime(9.3,[540.0,1273.0]);
tl.position.setValueAtTime(9.3+0.4,[540.0,1248.0]);
tl.scale.setValueAtTime(9.3,[200,200]);
tl.opacity.setValueAtTime(9.3,0);
tl.rotation.setValueAtTime(9.3,-8);
tl.scale.setValueAtTime(9.48,[100,100]);
tl.opacity.setValueAtTime(9.48,100);
tl.scale.setValueAtTime(9.6,[108,108]);
tl.opacity.setValueAtTime(9.6,100);
tl.scale.setValueAtTime(9.7,[100,100]);
tl.opacity.setValueAtTime(9.7,100);
tl.opacity.setValueAtTime(9.3,0);
tl.opacity.setValueAtTime(9.3+0.2,100);
tl.opacity.setValueAtTime(9.7-0.2,100);
tl.opacity.setValueAtTime(9.7,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZJingHeiS-R-GB',text:'战',start:9.3,end:9.7};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Drop :: drop_battle_cn :: 斗 ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("斗");
tl.name="TXT_sub_cn_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZJingHeiS-R-GB";
td.fontSize=130;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[1.000,0.133,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=10.4;tl.inPoint=10.4;tl.outPoint=10.8;
tl.position.setValueAtTime(10.4,[540.0,1273.0]);
tl.position.setValueAtTime(10.4+0.4,[540.0,1248.0]);
tl.scale.setValueAtTime(10.4,[200,200]);
tl.opacity.setValueAtTime(10.4,0);
tl.rotation.setValueAtTime(10.4,-8);
tl.scale.setValueAtTime(10.58,[100,100]);
tl.opacity.setValueAtTime(10.58,100);
tl.scale.setValueAtTime(10.7,[108,108]);
tl.opacity.setValueAtTime(10.7,100);
tl.scale.setValueAtTime(10.8,[100,100]);
tl.opacity.setValueAtTime(10.8,100);
tl.opacity.setValueAtTime(10.4,0);
tl.opacity.setValueAtTime(10.4+0.2,100);
tl.opacity.setValueAtTime(10.8-0.2,100);
tl.opacity.setValueAtTime(10.8,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZJingHeiS-R-GB',text:'斗',start:10.4,end:10.8};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Drop :: drop_battle_cn :: 提尔芬 ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("提尔芬");
tl.name="TXT_sub_cn_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZJingHeiS-R-GB";
td.fontSize=80;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[1.000,0.133,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=11.2;tl.inPoint=11.2;tl.outPoint=12.0;
tl.position.setValueAtTime(11.2,[540.0,1273.0]);
tl.position.setValueAtTime(11.2+0.4,[540.0,1248.0]);
tl.scale.setValueAtTime(11.2,[0,0]);
tl.opacity.setValueAtTime(11.2,0);
tl.scale.setValueAtTime(11.32,[108,108]);
tl.opacity.setValueAtTime(11.32,100);
tl.scale.setValueAtTime(11.55,[98,98]);
tl.opacity.setValueAtTime(11.55,100);
tl.scale.setValueAtTime(11.7,[100,100]);
tl.opacity.setValueAtTime(11.7,100);
tl.opacity.setValueAtTime(11.2,0);
tl.opacity.setValueAtTime(11.2+0.2,100);
tl.opacity.setValueAtTime(12.0-0.2,100);
tl.opacity.setValueAtTime(12.0,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZJingHeiS-R-GB',text:'提尔芬',start:11.2,end:12.0};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Drop :: drop_battle_cn :: 蛇 ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("蛇");
tl.name="TXT_sub_cn_impact";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZJingHeiS-R-GB";
td.fontSize=130;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[1.000,0.133,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=13.5;tl.inPoint=13.5;tl.outPoint=13.9;
tl.position.setValueAtTime(13.5,[540.0,1273.0]);
tl.position.setValueAtTime(13.5+0.4,[540.0,1248.0]);
tl.scale.setValueAtTime(13.5,[200,200]);
tl.opacity.setValueAtTime(13.5,0);
tl.rotation.setValueAtTime(13.5,-8);
tl.scale.setValueAtTime(13.68,[100,100]);
tl.opacity.setValueAtTime(13.68,100);
tl.scale.setValueAtTime(13.8,[108,108]);
tl.opacity.setValueAtTime(13.8,100);
tl.scale.setValueAtTime(13.9,[100,100]);
tl.opacity.setValueAtTime(13.9,100);
tl.opacity.setValueAtTime(13.5,0);
tl.opacity.setValueAtTime(13.5+0.2,100);
tl.opacity.setValueAtTime(13.9-0.2,100);
tl.opacity.setValueAtTime(13.9,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZJingHeiS-R-GB',text:'蛇',start:13.5,end:13.9};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Break :: break_memory :: 战争之后…… ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("战争之后……");
tl.name="TXT_serif_cn_classic";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="NotoSerifSC-VF";
td.fontSize=40;
td.applyFill=true;td.fillColor=[0.910,0.863,0.769];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=0.5;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=15.5;tl.inPoint=15.5;tl.outPoint=17.5;
tl.position.setValueAtTime(15.5,[540.0,985.0]);
tl.position.setValueAtTime(15.5+0.4,[540.0,960.0]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(15.5,0);
tl.opacity.setValueAtTime(15.5+0.2,100);
tl.opacity.setValueAtTime(17.5-0.2,100);
tl.opacity.setValueAtTime(17.5,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'NotoSerifSC-VF',text:'战争之后……',start:15.5,end:17.5};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Break :: break_quote :: REDEMPTION ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("REDEMPTION");
tl.name="TXT_serif_en_playfair";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="PlayfairDisplay-Bold";
td.fontSize=30;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=0.8;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=17.0;tl.inPoint=17.0;tl.outPoint=18.8;
tl.position.setValueAtTime(17.0,[540.0,1100.2]);
tl.position.setValueAtTime(17.0+0.4,[540.0,1075.2]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(17.0,0);
tl.opacity.setValueAtTime(17.0+0.2,100);
tl.opacity.setValueAtTime(18.8-0.2,100);
tl.opacity.setValueAtTime(18.8,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'PlayfairDisplay-Bold',text:'REDEMPTION',start:17.0,end:18.8};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Outro :: outro_hero :: VINLAND SAGA ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("VINLAND SAGA");
tl.name="TXT_hero_cn_brutal";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZLanTingHeiS-ExtraBold";
td.fontSize=80;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=19.5;tl.inPoint=19.5;tl.outPoint=22.5;
tl.position.setValueAtTime(19.5,[540.0,754.6]);
tl.position.setValueAtTime(19.5+0.4,[540.0,729.6]);
tl.scale.setValueAtTime(19.5,[0,0]);
tl.opacity.setValueAtTime(19.5,0);
tl.scale.setValueAtTime(19.62,[108,108]);
tl.opacity.setValueAtTime(19.62,100);
tl.scale.setValueAtTime(19.85,[98,98]);
tl.opacity.setValueAtTime(19.85,100);
tl.scale.setValueAtTime(20.0,[100,100]);
tl.opacity.setValueAtTime(20.0,100);
tl.opacity.setValueAtTime(19.5,0);
tl.opacity.setValueAtTime(19.5+0.2,100);
tl.opacity.setValueAtTime(22.5-0.2,100);
tl.opacity.setValueAtTime(22.5,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZLanTingHeiS-ExtraBold',text:'VINLAND SAGA',start:19.5,end:22.5};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Outro :: outro_hero :: 冰 海 战 记 ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("冰 海 战 记");
tl.name="TXT_hero_cn_brutal";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="FZLanTingHeiS-ExtraBold";
td.fontSize=50;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=2.0;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=20.0;tl.inPoint=20.0;tl.outPoint=22.5;
tl.position.setValueAtTime(20.0,[540.0,908.2]);
tl.position.setValueAtTime(20.0+0.4,[540.0,883.2]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(20.0,0);
tl.opacity.setValueAtTime(20.0+0.2,100);
tl.opacity.setValueAtTime(22.5-0.2,100);
tl.opacity.setValueAtTime(22.5,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'FZLanTingHeiS-ExtraBold',text:'冰 海 战 记',start:20.0,end:22.5};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Outro :: outro_credit :: — FIN — ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("— FIN —");
tl.name="TXT_credit_cn_puhui";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="AlibabaPuHuiTi-3-45-Light";
td.fontSize=36;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=0.2;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=21.5;tl.inPoint=21.5;tl.outPoint=23.0;
tl.position.setValueAtTime(21.5,[540.0,1081.0]);
tl.position.setValueAtTime(21.5+0.4,[540.0,1056.0]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(21.5,0);
tl.opacity.setValueAtTime(21.5+0.2,100);
tl.opacity.setValueAtTime(23.0-0.2,100);
tl.opacity.setValueAtTime(23.0,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'AlibabaPuHuiTi-3-45-Light',text:'— FIN —',start:21.5,end:23.0};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();

// === Outro :: outro_credit :: Director: Vinland Saga Team ===
(function(){var _r={};try{
var c=app.project.activeItem;
if(!c||!(c instanceof CompItem)){_r={status:'error',message:'No active comp'};return JSON.stringify(_r);}
var tl=c.layers.addText("Director: Vinland Saga Team");
tl.name="TXT_credit_cn_puhui";
var tp=tl.property("ADBE Text Properties").property("ADBE Text Document");
var td=tp.value;
td.font="AlibabaPuHuiTi-3-45-Light";
td.fontSize=18;
td.applyFill=true;td.fillColor=[1.000,1.000,1.000];
td.applyStroke=true;td.strokeColor=[0.000,0.000,0.000];
td.strokeWidth=0.2;
td.strokeOverFill=false;
td.justification=ParagraphJustification.CENTER_JUSTIFY;
tp.setValue(td);
tl.startTime=22.3;tl.inPoint=22.3;tl.outPoint=23.1;
tl.position.setValueAtTime(22.3,[540.0,1791.4]);
tl.position.setValueAtTime(22.3+0.4,[540.0,1766.4]);
try{tl.property("ADBE Text Properties").property("ADBE Text Document").expression="var td=value;td.tracking=linear(time-thisProperty.propertyGroup(3).startTime,0,0.5,30,0);td;";}catch(e_anim){}
tl.opacity.setValueAtTime(22.3,0);
tl.opacity.setValueAtTime(22.3+0.2,100);
tl.opacity.setValueAtTime(23.1-0.2,100);
tl.opacity.setValueAtTime(23.1,0);
try{
var glow=tl.property("Effects").addProperty("ADBE Glow");
glow.property("Glow Threshold").setValue(30);
glow.property("Glow Radius").setValue(20);
glow.property("Glow Intensity").setValue(0.7);
}catch(e_g){}
_r={status:'success',font:'AlibabaPuHuiTi-3-45-Light',text:'Director: Vinland Saga Team',start:22.3,end:23.1};
}catch(e){_r={status:'error',message:e.toString()};}
return JSON.stringify(_r);})();
_r.status="success";_r.textBlocks=18;
}catch(e){_r={status:"error",message:e.toString()};}
return JSON.stringify(_r);})();