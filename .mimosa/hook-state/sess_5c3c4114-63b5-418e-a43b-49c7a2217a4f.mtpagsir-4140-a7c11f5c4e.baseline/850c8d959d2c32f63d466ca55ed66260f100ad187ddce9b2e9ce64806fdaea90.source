# Silhouette fx API 验证 - 逐步排查版
from fx import *
import os
import traceback

class TestFxAPI(Action):
	def __init__(self):
		Action.__init__(self, "Test|Test Fx API v2")
	
	def execute(self):
		output_path = os.path.join(os.path.expanduser("~"), "Documents", "ae-mcp-bridge", "fx_action_result.txt")
		
		with open(output_path, "w", encoding="utf-8") as f:
			f.write("=== Silhouette fx API Test v2 ===\n\n")
			
			# Test 1: Point
			try:
				p = Point(100, 200)
				f.write(f"[PASS] Point(100,200): ({p.x}, {p.y})\n")
			except Exception as e:
				f.write(f"[FAIL] Point: {e}\n")
			
			# Test 2: Size
			try:
				s = Size(1920, 1080)
				f.write(f"[PASS] Size(1920,1080): ({s.width}, {s.height})\n")
			except Exception as e:
				f.write(f"[FAIL] Size: {e}\n")
			
			# Test 3: Recti
			try:
				r = Recti(0, 0, 1920, 1080)
				f.write(f"[PASS] Recti(0,0,1920,1080): left={r.left}, top={r.top}, right={r.right}, bottom={r.bottom}\n")
			except Exception as e:
				f.write(f"[FAIL] Recti: {e}\n")
			
			# Test 4: Property
			try:
				prop = Property("test_prop", 42)
				f.write(f"[PASS] Property: name={prop.name}, value={prop.value}\n")
			except Exception as e:
				f.write(f"[FAIL] Property: {e}\n")
			
			# Test 5: Object - 尝试不同构造方式
			try:
				obj = Object()
				f.write(f"[PASS] Object() created\n")
			except Exception as e:
				f.write(f"[FAIL] Object(): {e}\n")
				try:
					obj = Object("TestType")
					f.write(f"[PASS] Object('TestType') created: type={obj.type}\n")
				except Exception as e2:
					f.write(f"[FAIL] Object('TestType'): {e2}\n")
			
			# Test 6: Node - 尝试不同构造方式
			try:
				node = Node("BlurNode")
				f.write(f"[PASS] Node('BlurNode'): type={node.type}\n")
				f.write(f"      inputs={len(node.inputs)}, outputs={len(node.outputs)}\n")
			except Exception as e:
				f.write(f"[FAIL] Node('BlurNode'): {e}\n")
				try:
					node = Node()
					node.type = "BlurNode"
					f.write(f"[PASS] Node() + type set: type={node.type}\n")
				except Exception as e2:
					f.write(f"[FAIL] Node(): {e2}\n")
			
			# Test 7: SourceNode
			try:
				src = Node("SourceNode")
				f.write(f"[PASS] Node('SourceNode'): inputs={len(src.inputs)}, outputs={len(src.outputs)}\n")
			except Exception as e:
				f.write(f"[FAIL] Node('SourceNode'): {e}\n")
			
			# Test 8: OutputNode
			try:
				out = Node("OutputNode")
				f.write(f"[PASS] Node('OutputNode'): inputs={len(out.inputs)}, outputs={len(out.outputs)}\n")
			except Exception as e:
				f.write(f"[FAIL] Node('OutputNode'): {e}\n")
			
			# Test 9: Pipe
			try:
				src = Node("SourceNode")
				blur = Node("BlurNode")
				pipe = Pipe(src.outputs[0], blur.inputs[0])
				f.write(f"[PASS] Pipe created\n")
			except Exception as e:
				f.write(f"[FAIL] Pipe: {e}\n")
			
			# Test 10: Project
			try:
				proj = Project()
				f.write(f"[PASS] Project() created\n")
			except Exception as e:
				f.write(f"[FAIL] Project(): {e}\n")
			
			# Test 11: Session
			try:
				session = Session()
				f.write(f"[PASS] Session() created\n")
			except Exception as e:
				f.write(f"[FAIL] Session(): {e}\n")
				try:
					session = Session("TestSession")
					f.write(f"[PASS] Session('TestSession') created: label={session.label}\n")
				except Exception as e2:
					f.write(f"[FAIL] Session('TestSession'): {e2}\n")
			
			# Test 12: 全局函数
			try:
				ver = version()
				f.write(f"[PASS] version() = {ver}\n")
			except Exception as e:
				f.write(f"[FAIL] version(): {e}\n")
			
			try:
				proj = activeProject()
				f.write(f"[PASS] activeProject() = {proj}\n")
			except Exception as e:
				f.write(f"[FAIL] activeProject(): {e}\n")
			
			try:
				sess = activeSession()
				f.write(f"[PASS] activeSession() = {sess}\n")
			except Exception as e:
				f.write(f"[FAIL] activeSession(): {e}\n")
			
			# Test 13: 检查 fx 模块有哪些可用符号
			import fx as fxmod
			symbols = [x for x in dir(fxmod) if not x.startswith('_')]
			f.write(f"\n--- Available fx symbols ({len(symbols)}) ---\n")
			for s in sorted(symbols):
				f.write(f"  {s}\n")
			
			f.write("\n=== Test Complete ===\n")

addAction(TestFxAPI())
