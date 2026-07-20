/**
 * Scheduler - 调度器
 * --------------------------------
 * 对IR节点进行拓扑排序, 确保执行顺序正确
 * 合成 → 图层 → 效果 → 关键帧/表达式 → 遮罩 → 混合模式/父子关系 → 轨道遮罩
 *
 * @module apc/scheduler
 */

import type { IRNode, IRNodeType } from "./types.js";

/**
 * 调度结果
 */
export interface ScheduleResult {
  sorted: IRNode[]; // 拓扑排序后的节点
  errors: Array<{ code: string; message: string }>;
}

// 操作优先级 (数字越小越先执行)
const OP_PRIORITY: Record<IRNodeType, number> = {
  createComp: 10,
  addLayer: 20,
  addEffect: 30,
  setProperty: 40,
  setKeyframe: 50,
  setExpression: 60,
  addMask: 70,
  setBlendMode: 80,
  setParent: 90,
  setTrackMatte: 100,
};

/**
 * 拓扑排序
 * 算法: Kahn's algorithm (BFS)
 */
export function schedule(nodes: IRNode[]): ScheduleResult {
  const errors: Array<{ code: string; message: string }> = [];

  // 1. 构建邻接表和入度表
  const inDegree = new Map<string, number>();
  const outEdges = new Map<string, string[]>();

  for (const node of nodes) {
    inDegree.set(node.id, 0);
    outEdges.set(node.id, []);
  }

  // 建立ID到节点的映射
  const nodeMap = new Map<string, IRNode>();
  for (const node of nodes) {
    nodeMap.set(node.id, node);
  }

  // 填充依赖关系
  for (const node of nodes) {
    for (const dep of node.deps) {
      if (outEdges.has(dep)) {
        outEdges.get(dep)!.push(node.id);
        inDegree.set(node.id, (inDegree.get(node.id) || 0) + 1);
      }
    }
  }

  // 2. 初始化队列: 入度为0的节点, 按优先级排序
  let queue = nodes.filter((n) => (inDegree.get(n.id) || 0) === 0);
  queue.sort((a, b) => (OP_PRIORITY[a.type] || 999) - (OP_PRIORITY[b.type] || 999));

  // 3. BFS拓扑排序
  const sorted: IRNode[] = [];
  let safetyCounter = nodes.length * 2;

  while (queue.length > 0 && safetyCounter > 0) {
    safetyCounter--;

    // 取出优先级最高的节点
    const node = queue.shift()!;
    sorted.push(node);

    // 减少后继节点的入度
    const outs = outEdges.get(node.id) || [];
    for (const nextId of outs) {
      const newDegree = (inDegree.get(nextId) || 0) - 1;
      inDegree.set(nextId, newDegree);

      if (newDegree === 0) {
        const nextNode = nodeMap.get(nextId);
        if (nextNode) {
          // 插入队列, 保持优先级排序
          insertByPriority(queue, nextNode);
        }
      }
    }
  }

  // 4. 检查循环依赖
  if (sorted.length < nodes.length) {
    const unresolved = nodes.filter((n) => !sorted.includes(n));
    errors.push({
      code: "S001",
      message: `检测到循环依赖, 无法解析的节点: ${unresolved.map((n) => n.id).join(", ")}`,
    });
    // 把未解析的节点按原顺序追加
    sorted.push(...unresolved);
  }

  return { sorted, errors };
}

/**
 * 按优先级插入节点到队列中
 */
function insertByPriority(queue: IRNode[], node: IRNode): void {
  const priority = OP_PRIORITY[node.type] || 999;
  let i = 0;
  while (i < queue.length && (OP_PRIORITY[queue[i].type] || 999) <= priority) {
    i++;
  }
  queue.splice(i, 0, node);
}
