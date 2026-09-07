/**
 * IR Builder - 中间表示构建器
 * ----------------------------------
 * 将验证过的JSON操作转换为IR节点, 并构建依赖图
 *
 * @module apc/ir-builder
 */

import type {
  CompilerInput,
  Operation,
  IRNode,
  CreateCompOp,
  AddLayerOp,
  AddEffectOp,
  SetPropertyOp,
  SetKeyframeOp,
  SetExpressionOp,
  AddMaskOp,
  SetBlendModeOp,
  SetParentOp,
  SetTrackMatteOp,
} from "./types.js";

/**
 * IR构建结果
 */
export interface IRBuildResult {
  nodes: IRNode[]; // 按输入顺序排列的节点
  refToNodeId: Map<string, string>; // ref -> nodeId 映射
  errors: Array<{ code: string; message: string }>;
}

/**
 * 构建IR
 * 输入: 验证过的操作序列
 * 输出: IR节点列表 + 引用映射表
 */
export function buildIR(input: CompilerInput): IRBuildResult {
  const nodes: IRNode[] = [];
  const refToNodeId = new Map<string, string>();
  const errors: Array<{ code: string; message: string }> = [];

  // 1. 第一遍: 为每个操作分配ID, 建立ref映射
  let counter = 0;
  for (const op of input.operations) {
    const nodeId = `node_${counter.toString(36).padStart(3, "0")}`;
    counter++;

    if (op.ref) {
      refToNodeId.set(op.ref, nodeId);
    }
  }

  // 2. 第二遍: 构建IR节点, 解析依赖关系
  counter = 0;
  for (const op of input.operations) {
    const nodeId = `node_${counter.toString(36).padStart(3, "0")}`;
    counter++;

    const deps = resolveDependencies(op, refToNodeId);

    nodes.push({
      id: nodeId,
      type: op.op,
      deps,
      source: op,
    });
  }

  return { nodes, refToNodeId, errors };
}

/**
 * 解析操作的依赖关系
 */
function resolveDependencies(op: Operation, refToNodeId: Map<string, string>): string[] {
  const deps: string[] = [];

  // 显式依赖
  if (op.dependsOn) {
    for (const dep of op.dependsOn) {
      const depId = refToNodeId.get(dep);
      if (depId && !deps.includes(depId)) {
        deps.push(depId);
      }
    }
  }

  // 隐式依赖 (根据操作类型推断)
  switch (op.op) {
    case "addLayer": {
      const layerOp = op as AddLayerOp;
      const compId = refToNodeId.get(layerOp.compRef);
      if (compId && !deps.includes(compId)) deps.push(compId);
      break;
    }
    case "addEffect": {
      const effectOp = op as AddEffectOp;
      const layerId = refToNodeId.get(effectOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setProperty": {
      const setPropOp = op as SetPropertyOp;
      const layerId = refToNodeId.get(setPropOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setKeyframe": {
      const kfOp = op as SetKeyframeOp;
      const layerId = refToNodeId.get(kfOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setExpression": {
      const exprOp = op as SetExpressionOp;
      const layerId = refToNodeId.get(exprOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "addMask": {
      const maskOp = op as AddMaskOp;
      const layerId = refToNodeId.get(maskOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setBlendMode": {
      const blendOp = op as SetBlendModeOp;
      const layerId = refToNodeId.get(blendOp.layerRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      break;
    }
    case "setParent": {
      const parentOp = op as SetParentOp;
      const layerId = refToNodeId.get(parentOp.layerRef);
      const parentId = refToNodeId.get(parentOp.parentRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      if (parentId && !deps.includes(parentId)) deps.push(parentId);
      break;
    }
    case "setTrackMatte": {
      const matteOp = op as SetTrackMatteOp;
      const layerId = refToNodeId.get(matteOp.layerRef);
      const matteLayerId = refToNodeId.get(matteOp.matteRef);
      if (layerId && !deps.includes(layerId)) deps.push(layerId);
      if (matteLayerId && !deps.includes(matteLayerId)) deps.push(matteLayerId);
      break;
    }
  }

  return deps;
}
