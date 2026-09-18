# Silhouette Roto 端到端测试 - 基于真实 API
import os
import traceback

from fx import *


class TestRotoE2E(Action):
	def __init__(self):
		Action.__init__(self, "Test|Roto E2E Test")
	
	def execute(self):
		output_path = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge", "roto_e2e_result.txt")
		
		with open(output_path, "w", encoding="utf-8") as f:
			f.write("=== Silhouette Roto E2E Test ===\n\n")
			
			# Step 1: 获取当前 Project（如果没有则创建）
			try:
				proj = activeProject()
				if proj is None:
					proj = Project()
					activate(proj)
					f.write(f"[1] Project created: {proj}\n")
				else:
					f.write(f"[1] Active Project: {proj}\n")
			except Exception as e:
				f.write(f"[1] FAIL: {e}\n")
				return
			
			# Step 2: 创建 Session
			try:
				session = Session()
				session.label = "RotoE2E"
				activate(session)
				proj.addItem(session)
				f.write(f"[2] Session created: {session.label}\n")
			except Exception as e:
				f.write(f"[2] FAIL: {e}\n")
				return
			
			# Step 3: 创建 Source 节点
			try:
				src = Node("SourceNode")
				f.write(f"[3] SourceNode created: {src}\n")
				f.write(f"    inputs={len(src.inputs)}, outputs={len(src.outputs)}\n")
				# 尝试设置路径
				test_image = r"C:\Temp\silhouette_test\roto_test_person.png"
				try:
					src.property("path").setValue(test_image, 0)
					f.write(f"    path set to: {test_image}\n")
				except Exception as e:
					f.write(f"    path set failed (expected): {e}\n")
			except Exception as e:
				f.write(f"[3] FAIL: {e}\n")
				return
			
			# Step 4: 获取可用节点类型
			try:
				node_infos = getNodes()
				f.write(f"\n[4] Available node types ({len(node_infos)}):\n")
				for n in node_infos:
					f.write(f"    {n}\n")
			except Exception as e:
				f.write(f"[4] getNodes() failed: {e}\n")
			
			# Step 5: 尝试创建 Roto 节点
			roto_node = None
			roto_types = ["RotoNode", "Roto", "roto", "ShapesNode", "ShapeNode"]
			for rt in roto_types:
				try:
					roto_node = Node(rt)
					f.write(f"\n[5] Roto node created with type '{rt}': {roto_node}\n")
					break
				except Exception:
					continue
			
			if roto_node is None:
				f.write("\n[5] Could not create Roto node by type name\n")
				f.write("    Will try addNode or createObject\n")
				try:
					roto_node = addNode("RotoNode")
					f.write(f"[5] addNode('RotoNode') created: {roto_node}\n")
				except Exception as e:
					f.write(f"[5] addNode failed: {e}\n")
			
			# Step 6: 创建 Output 节点
			try:
				out_node = Node("OutputNode")
				f.write(f"\n[6] OutputNode created: {out_node}\n")
				f.write(f"    inputs={len(out_node.inputs)}, outputs={len(out_node.outputs)}\n")
			except Exception as e:
				f.write(f"[6] FAIL: {e}\n")
			
			# Step 7: 尝试连接节点
			if src and roto_node:
				try:
					# 方法1: Pipe
					pipe = Pipe(src.outputs[0], roto_node.inputs[0])
					f.write("\n[7] Pipe Source→Roto created\n")
				except Exception as e:
					f.write(f"\n[7] Pipe failed: {e}\n")
					# 方法2: connect
					try:
						src.outputs[0].connect(roto_node.inputs[0])
						f.write("[7] connect() method worked\n")
					except Exception as e2:
						f.write(f"[7] connect() also failed: {e2}\n")
			
			if roto_node and out_node:
				try:
					pipe2 = Pipe(roto_node.outputs[0], out_node.inputs[0])
					f.write("[7] Pipe Roto→Output created\n")
				except Exception as e:
					f.write(f"[7] Pipe Roto→Output failed: {e}\n")
			
			# Step 8: 尝试添加节点到 Session
			try:
				session.addNode(src)
				f.write("\n[8] Source added to session\n")
			except Exception as e:
				f.write(f"[8] addNode(src) failed: {e}\n")
				try:
					session.addItem(src)
					f.write("[8] addItem(src) worked\n")
				except Exception as e2:
					f.write(f"[8] addItem also failed: {e2}\n")
			
			# Step 9: 检查节点信息
			try:
				info = getNodeInfo(src)
				f.write(f"\n[9] NodeInfo for Source: {info}\n")
			except Exception as e:
				f.write(f"[9] getNodeInfo failed: {e}\n")
			
			# Step 10: 版本信息
			try:
				f.write(f"\n[10] version={version}\n")
				f.write(f"     versionString={versionString}\n")
				f.write(f"     versionMajor={versionMajor}\n")
				f.write(f"     versionMinor={versionMinor}\n")
				f.write(f"     buildNumber={buildNumber}\n")
			except Exception as e:
				f.write(f"[10] version info failed: {e}\n")
			
			# Step 11: 列出所有节点类型（用 getNodeInfo）
			try:
				node_types = getNodes()
				f.write("\n[11] All node types:\n")
				for nt in node_types:
					f.write(f"    {nt}\n")
			except Exception as e:
				f.write(f"[11] getNodes failed: {e}\n")
			
			f.write("\n=== Roto E2E Test Complete ===\n")

addAction(TestRotoE2E())
