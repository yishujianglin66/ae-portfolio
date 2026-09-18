# Silhouette Roto 管线测试 - 连接修复版
import os

from fx import *


class TestRotoPipeline(Action):
	def __init__(self):
		Action.__init__(self, "Test|Roto Pipeline")
	
	def execute(self):
		output_path = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge", "roto_pipeline_result.txt")
		
		with open(output_path, "w", encoding="utf-8") as f:
			f.write("=== Silhouette Roto Pipeline Test ===\n\n")
			
			# Step 1: 获取或创建 session
			try:
				sess = activeSession()
				if sess is None:
					proj = activeProject() or Project()
					activate(proj)
					sess = Session()
					sess.label = "RotoPipeline"
					activate(sess)
					proj.addItem(sess)
				f.write(f"[1] Session: {sess.label}\n")
			except Exception as e:
				f.write(f"[1] FAIL: {e}\n")
				return
			
			# Step 2: 创建所有节点
			f.write("\n[2] Creating nodes:\n")
			
			try:
				src = Node("SourceNode")
				f.write("  SourceNode: OK\n")
				f.write(f"    outputs: {[o.name for o in src.outputs]}\n")
			except Exception as e:
				f.write(f"  SourceNode FAIL: {e}\n")
				src = None
			
			try:
				roto = Node("RotoNode")
				f.write("  RotoNode: OK\n")
				f.write(f"    inputs: {[i.name for i in roto.inputs]}\n")
				f.write(f"    outputs: {[o.name for o in roto.outputs]}\n")
			except Exception as e:
				f.write(f"  RotoNode FAIL: {e}\n")
				roto = None
			
			try:
				out_node = Node("OutputNode")
				f.write("  OutputNode: OK\n")
				f.write(f"    inputs: {[i.name for i in out_node.inputs]}\n")
			except Exception as e:
				f.write(f"  OutputNode FAIL: {e}\n")
				out_node = None
			
			# Step 3: 测试节点连接方法
			f.write("\n[3] Testing node connection:\n")
			
			if src and roto:
				# 方法1: 直接赋值
				try:
					roto.inputs[0].source = src.outputs[0]
					f.write("  Method1: roto.inputs[0].source = src.outputs[0] : OK\n")
				except Exception as e:
					f.write(f"  Method1 FAIL: {e}\n")
				
				# 方法2: connect 方法
				try:
					src.outputs[0].connect(roto.inputs[0])
					f.write("  Method2: src.outputs[0].connect(roto.inputs[0]) : OK\n")
				except Exception as e:
					f.write(f"  Method2 FAIL: {e}\n")
				
				# 方法3: 检查连接状态
				try:
					connected = roto.inputs[0].source is not None
					f.write(f"  Connection status: {connected}\n")
				except Exception as e:
					f.write(f"  Connection check FAIL: {e}\n")
			
			if roto and out_node:
				try:
					out_node.inputs[0].source = roto.outputs[0]
					f.write("  Roto→Output: OK\n")
				except Exception as e:
					f.write(f"  Roto→Output FAIL: {e}\n")
			
			# Step 4: 添加到 session
			f.write("\n[4] Adding to session:\n")
			for node in [src, roto, out_node]:
				if node:
					try:
						sess.addNode(node)
						f.write(f"  {node.type}: added\n")
					except Exception as e:
						f.write(f"  {node.type} addNode FAIL: {e}\n")
			
			# Step 5: 检查连接状态
			f.write("\n[5] Final connection status:\n")
			if roto:
				for i, inp in enumerate(roto.inputs):
					try:
						source = inp.source
						f.write(f"  Roto input[{i}] {inp.name}: source={source}\n")
					except Exception as e:
						f.write(f"  Roto input[{i}] check FAIL: {e}\n")
			
			# Step 6: 测试 Roto 属性
			f.write("\n[6] Roto properties:\n")
			if roto:
				try:
					props = roto.properties
					f.write(f"  Properties ({len(props)}):\n")
					for p in props:
						try:
							prop_obj = roto.property(p)
							f.write(f"    {p}: {prop_obj}\n")
						except Exception as e:
							f.write(f"    {p}: error={e}\n")
				except Exception as e:
					f.write(f"  Properties access FAIL: {e}\n")
			
			# Step 7: 测试设置 Source 路径
			f.write("\n[7] Testing Source path:\n")
			if src:
				try:
					test_path = r"C:\Temp\silhouette_test\roto_test_person.png"
					src.property("path").setValue(test_path, 0)
					f.write(f"  Source path set to: {test_path}\n")
					# 验证
					current_path = src.property("path").getValue(0)
					f.write(f"  Current path: {current_path}\n")
				except Exception as e:
					f.write(f"  Path set FAIL: {e}\n")
			
			f.write("\n=== Test Complete ===\n")

addAction(TestRotoPipeline())
