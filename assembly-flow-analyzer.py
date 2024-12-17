from dataclasses import dataclass
from typing import Dict, Set, List, Optional, Tuple
import re
from pathlib import Path
from enum import Enum, auto

class BlockType(Enum):
    NORMAL = auto()
    CONDITIONAL = auto()
    LOOP_HEADER = auto()
    LOOP_BODY = auto()
    FUNCTION_ENTRY = auto()
    FUNCTION_EXIT = auto()

@dataclass
class BasicBlock:
    id: int
    type: BlockType
    start_line: int
    end_line: int
    code: List[str]
    successors: Set[int]  # 後続ブロックのID
    predecessors: Set[int]  # 先行ブロックのID
    conditions: Set[str]  # 分岐条件 (e.g., "EQ", "GT")

@dataclass
class Function:
    name: str
    start_line: int
    end_line: int
    code_block: str
    direct_calls: Set[str]
    register_usage: Set[str]
    basic_blocks: Dict[int, BasicBlock]  # ブロックID → BasicBlock
    entry_block: int  # エントリーブロックのID
    exit_blocks: Set[int]  # 出口ブロックのIDセット
    loops: Set[Tuple[int, Set[int]]]  # (ループヘッダID, ループ内ブロックID)のセット

class ControlFlowAnalyzer:
    def __init__(self):
        self.branch_instructions = {
            'BRA': None,   # 無条件分岐
            'BEQ': 'EQ',   # = の時分岐
            'BNE': 'NE',   # ≠ の時分岐
            'BGT': 'GT',   # > の時分岐
            'BGE': 'GE',   # ≥ の時分岐
            'BLT': 'LT',   # < の時分岐
            'BLE': 'LE',   # ≤ の時分岐
            'BPL': 'PL',   # ≥ 0 の時分岐
            'BMI': 'MI'    # < 0 の時分岐
        }
        self.next_block_id = 0

    def analyze_function(self, func: Function) -> None:
        """関数の制御フローを解析"""
        # 基本ブロックの特定
        blocks = self._identify_basic_blocks(func)
        func.basic_blocks = blocks
        
        # エントリー/出口ブロックの設定
        func.entry_block = min(blocks.keys())
        func.exit_blocks = {
            bid for bid, block in blocks.items()
            if not block.successors or any('RTS' in line for line in block.code)
        }
        
        # ループの検出
        func.loops = self._identify_loops(blocks)
        
        # ブロックタイプの更新
        self._update_block_types(blocks, func.loops)

    def _identify_basic_blocks(self, func: Function) -> Dict[int, BasicBlock]:
        """基本ブロックの特定と分割"""
        lines = func.code_block.splitlines()
        blocks: Dict[int, BasicBlock] = {}
        current_lines = []
        current_start = 0
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # ラベルの検出
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*:', line):
                if current_lines:
                    block = self._create_block(
                        current_start, i-1, current_lines, BlockType.NORMAL
                    )
                    blocks[block.id] = block
                    current_lines = []
                current_start = i
            
            current_lines.append(line)
            
            # 分岐命令の検出
            if any(instr in line for instr in self.branch_instructions.keys()):
                if current_lines:
                    block = self._create_block(
                        current_start, i, current_lines, BlockType.CONDITIONAL
                    )
                    blocks[block.id] = block
                    current_lines = []
                current_start = i + 1
        
        # 最後のブロック
        if current_lines:
            block = self._create_block(
                current_start, len(lines)-1, current_lines, BlockType.NORMAL
            )
            blocks[block.id] = block
        
        # ブロック間の接続関係を解析
        self._connect_blocks(blocks, lines)
        
        return blocks

    def _create_block(self, start: int, end: int, lines: List[str], 
                     type: BlockType) -> BasicBlock:
        """新しい基本ブロックを作成"""
        block_id = self.next_block_id
        self.next_block_id += 1
        
        return BasicBlock(
            id=block_id,
            type=type,
            start_line=start,
            end_line=end,
            code=lines,
            successors=set(),
            predecessors=set(),
            conditions=set()
        )

    def _connect_blocks(self, blocks: Dict[int, BasicBlock], 
                       full_code: List[str]) -> None:
        """ブロック間の接続関係を解析"""
        for block in blocks.values():
            last_line = block.code[-1].strip()
            
            # 分岐命令の解析
            for instr, condition in self.branch_instructions.items():
                if instr in last_line:
                    # 分岐先ラベルの取得
                    match = re.search(rf'{instr}\s+([A-Za-z_][A-Za-z0-9_]*)', last_line)
                    if match:
                        target_label = match.group(1)
                        # 分岐先ブロックを見つける
                        for target in blocks.values():
                            if f'{target_label}:' in target.code[0]:
                                block.successors.add(target.id)
                                target.predecessors.add(block.id)
                                if condition:
                                    block.conditions.add(condition)
                    
                    # BRA以外は次のブロックも後続となる
                    if instr != 'BRA':
                        next_block = self._find_next_block(blocks, block)
                        if next_block:
                            block.successors.add(next_block.id)
                            next_block.predecessors.add(block.id)
                    break
            else:
                # 分岐命令がない場合は次のブロックに接続
                next_block = self._find_next_block(blocks, block)
                if next_block and not any('RTS' in line for line in block.code):
                    block.successors.add(next_block.id)
                    next_block.predecessors.add(block.id)

    def _find_next_block(self, blocks: Dict[int, BasicBlock], 
                        current: BasicBlock) -> Optional[BasicBlock]:
        """現在のブロックの次のブロックを見つける"""
        next_line = current.end_line + 1
        return next(
            (block for block in blocks.values() if block.start_line == next_line),
            None
        )

    def _identify_loops(self, blocks: Dict[int, BasicBlock]) -> Set[Tuple[int, Set[int]]]:
        """ループ構造の検出"""
        loops = set()
        visited = set()
        
        def dfs(block_id: int, path: Set[int]) -> None:
            if block_id in path:
                # バックエッジを検出
                loop_header = block_id
                loop_blocks = self._find_loop_blocks(blocks, loop_header, path)
                loops.add((loop_header, loop_blocks))
                return
            
            if block_id in visited:
                return
            
            visited.add(block_id)
            path.add(block_id)
            
            for succ in blocks[block_id].successors:
                dfs(succ, path.copy())
        
        # エントリーブロックからDFSを開始
        dfs(min(blocks.keys()), set())
        return loops

    def _find_loop_blocks(self, blocks: Dict[int, BasicBlock], 
                         header: int, path: Set[int]) -> Set[int]:
        """ループに含まれるブロックを特定"""
        loop_blocks = {header}
        queue = [header]
        
        while queue:
            current = queue.pop(0)
            for succ in blocks[current].successors:
                if succ not in loop_blocks and (
                    succ in path or any(
                        pred in loop_blocks for pred in blocks[succ].predecessors
                    )
                ):
                    loop_blocks.add(succ)
                    queue.append(succ)
        
        return loop_blocks

    def _update_block_types(self, blocks: Dict[int, BasicBlock], 
                          loops: Set[Tuple[int, Set[int]]]) -> None:
        """ブロックタイプを更新"""
        # ループ関連のブロックタイプを設定
        for header, loop_blocks in loops:
            blocks[header].type = BlockType.LOOP_HEADER
            for block_id in loop_blocks - {header}:
                blocks[block_id].type = BlockType.LOOP_BODY

        # エントリー/出口ブロックの設定
        entry_id = min(blocks.keys())
        blocks[entry_id].type = BlockType.FUNCTION_ENTRY
        
        for block in blocks.values():
            if not block.successors or any('RTS' in line for line in block.code):
                block.type = BlockType.FUNCTION_EXIT

class AssemblyAnalyzer:
    def __init__(self):
        self.functions: Dict[str, Function] = {}
        self.call_graph: Dict[str, Set[str]] = {}
        self.reverse_call_graph: Dict[str, Set[str]] = {}
        self.flow_analyzer = ControlFlowAnalyzer()
    
    def load_file(self, filepath: Path) -> None:
        """アセンブリファイルを読み込んで解析"""
        # [前のコードと同じ]
        pass
    
    def analyze_control_flow(self, func_name: str) -> None:
        """指定された関数の制御フローを解析"""
        func = self.functions.get(func_name)
        if func:
            self.flow_analyzer.analyze_function(func)
    
    def print_control_flow(self, func_name: str) -> None:
        """制御フロー解析の結果を表示"""
        func = self.functions.get(func_name)
        if not func:
            print(f"Function {func_name} not found")
            return
        
        print(f"Control Flow Analysis for {func_name}:")
        print("\nBasic Blocks:")
        for block in func.basic_blocks.values():
            print(f"\nBlock {block.id} ({block.type.name}):")
            print(f"Lines {block.start_line}-{block.end_line}")
            print(f"Predecessors: {block.predecessors}")
            print(f"Successors: {block.successors}")
            if block.conditions:
                print(f"Conditions: {block.conditions}")
            print("Code:")
            for line in block.code:
                print(f"  {line}")
        
        print("\nLoops:")
        for header, blocks in func.loops:
            print(f"Loop with header block {header}:")
            print(f"Loop blocks: {blocks}")

def main():
    # サンプル使用
    sample_asm = """
LOOP_EXAMPLE:
        PUSH.L R6-R8
        MOV.L #0, R6      ; カウンタ初期化
LOOP_START:
        CMP.L #10, R6     ; カウンタチェック
        BGE LOOP_END      ; 10以上なら終了
        
        MOV.L R6, R1      ; 処理
        JSR PROCESS_DATA
        
        ADD.L #1, R6      ; カウンタインクリメント
        BRA LOOP_START    ; ループ先頭に戻る
        
LOOP_END:
        MOV.L R6, R1      ; 結果を返す
        POP.L R6-R8
        RTS

PROCESS_DATA:
        CMP.L #0, R1
        BMI NEGATIVE      ; 負数の場合
        ADD.L #1, R1      ; 正数の場合は+1
        RTS
NEGATIVE:
        SUB.L #1, R1      ; 負数の場合は-1
        RTS
"""
    # テスト用の一時ファイルを作成と解析
    test_file = Path("test.asm")
    test_file.write_text(sample_asm)
    
    analyzer = AssemblyAnalyzer()
    analyzer.load_file(test_file)
    analyzer.analyze_control_flow("LOOP_EXAMPLE")
    analyzer.print_control_flow("LOOP_EXAMPLE")
    
    test_file.unlink()

if __name__ == "__main__":
    main()
