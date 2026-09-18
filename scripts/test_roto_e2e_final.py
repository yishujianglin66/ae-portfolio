# Silhouette Roto 端到端测试 - 完整管线
import os

from fx import *


class TestRotoE2E(Action):
	def __init__(self):
		Action.__init__(self, "Test|Roto E2E")
	
	def execute(self):
		output_path = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge", "roto_e2e_final.txt")
		
		with open(output_path, "w", encoding="utf-8") as f:
			f.write("=== Silhouette Roto E2E Test ===\n\n")
			
			# Step 1: 创建/获取 Session
			try:
				sess = activeSession()
				if sess is None:
					proj = activeProject() or Project()
					activate(proj)
					sess = Session()
					sess.label = "RotoE2E_Final"
					activate(sess)
					proj.addItem(sess)
				f.write(f"[1] Session: {sess.label}\n")
			except Exception as e:
				f.write(f"[1] FAIL: {e}\n")
				return
			
			# Step 2: 创建节点
			f.write("\n[2] Creating nodes:\n")
			
			src = Node("SourceNode")
			f.write("  SourceNode: OK\n")
			
			roto = Node("RotoNode")
			f.write("  RotoNode: OK\n")
			
			out_node = Node("OutputNode")
			f.write("  OutputNode: OK\n")
			
			# Step 3: 正确连接节点
			f.write("\n[3] Connecting nodes:\n")
			
			# Source → Roto (连接到 foreground 端口)
			try:
				src.outputs[0].connect(roto.inputs[1])  # inputs[1] = foreground
				f.write("  Source.output → Roto.foreground: OK\n")
			except Exception as e:
				f.write(f"  Source→Roto FAIL: {e}\n")
			
			# Roto → Output
			try:
				roto.outputs[0].connect(out_node.inputs[0])  # outputs[0] = output
				f.write("  Roto.output → Output.input: OK\n")
			except Exception as e:
				f.write(f"  Roto→Output FAIL: {e}\n")
			
			# Step 4: 添加到 session
			f.write("\n[4] Adding to session:\n")
			sess.addNode(src)
			sess.addNode(roto)
			sess.addNode(out_node)
			f.write("  All nodes added\n")
			
			# Step 5: 测试设置 Source 文件路径的正确方式
			f.write("\n[5] Setting Source media:\n")
			
			test_image = r"C:\Temp\silhouette_test\roto_test_person.png"
			
			try:
				# 方法1: 检查所有属性
				props = src.properties
				f.write(f"  Source properties: {props}\n")
				
				# 尝试用不同方式设置路径
				if 'path' in props:
					try:
						path_prop = src.property('path')
						f.write(f"  path property: {path_prop}\n")
						path_prop.setValue(test_image, 0)
						f.write("  Path set via setValue: OK\n")
					except Exception as e:
						f.write(f"  setValue FAIL: {e}\n")
				
				# 方法2: 直接设置属性
				try:
					src.path = test_image
					f.write("  Path set via src.path: OK\n")
				except Exception as e:
					f.write(f"  src.path FAIL: {e}\n")
				
				# 方法3: 使用 importMedia
				try:
					importMedia(test_image)
					f.write(f"  importMedia({test_image}): OK\n")
				except Exception as e:
					f.write(f"  importMedia FAIL: {e}\n")
				
				# 方法4: 检查 Source 属性
				try:
					if hasattr(src, 'media'):
						f.write(f"  src.media: {src.media}\n")
					if hasattr(src, 'file'):
						f.write(f"  src.file: {src.file}\n")
				except Exception as e:
					f.write(f"  Attribute check FAIL: {e}\n")
				
			except Exception as e:
				f.write(f"  Path setting FAIL: {e}\n")
			
			# Step 6: 检查最终连接状态
			f.write("\n[6] Final connection status:\n")
			f.write(f"  Roto.foreground source: {roto.inputs[1].source}\n")
			f.write(f"  Output.input source: {out_node.inputs[0].source}\n")
			
			# Step 7: 列出所有节点
			try:
				nodes = sess.nodes
				f.write(f"\n[7] Session nodes ({len(nodes)}):\n")
				for n in nodes:
					f.write(f"  - {n.type}: {n.label}\n")
			except Exception as e:
				f.write(f"[7] Session nodes FAIL: {e}\n")
			
			f.write("\n=== Roto E2E Test Complete ===\n")

addAction(TestRotoE2E())
