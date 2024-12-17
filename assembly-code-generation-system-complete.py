from dataclasses import dataclass
from typing import Dict, List, Set, Optional
import re

# データ構造の定義
@dataclass
class CodeLocation:
    file: str
    start_line: int
    end_line: int

@dataclass
class RegisterContext:
    input_regs: Set[str]
    output_regs: Set[str]
    preserved_regs: Set[str]
    modified_regs: Set[str]

@dataclass
class Function:
    name: str
    location: CodeLocation
    registers_used: Set[str]
    calls: Set[str]
    called_by: Set[str]
    symbols_used: Set[str]

@dataclass
class Symbol:
    name: str
    location: CodeLocation
    type: str
    value: Optional[str]
    used_by: Set[str]

@dataclass
class FunctionContext:
    name: str
    code_block: str
    register_usage: RegisterContext
    calls: List[str]
    called_by: List[str]
    stack_usage: int

# コードベース管理
class CodebaseManager:
    def __init__(self):
        self.files: Dict[str, List[str]] = {}
        self.functions: Dict[str, Function] = {}
        self.symbols: Dict[str, Symbol] = {}
        
    def load_file(self, filepath: str):
        """ソースファイルを読み込み、基本解析を行う"""
        with open(filepath, 'r') as f:
            lines = f.readlines()
        self.files[filepath] = lines
        self._initial_parse(filepath, lines)

    def _initial_parse(self, filepath: str, lines: List[str]):
        """基本的なシンボルと関数の抽出"""
        current_function = None
        for i, line in enumerate(lines):
            if re.match(r'^\s*[A-Za-z_][A-Za-z0-9_]*:', line):
                # 関数ラベルの検出
                func_name = line.strip().rstrip(':')
                current_function = Function(
                    name=func_name,
                    location=CodeLocation(filepath, i, i),
                    registers_used=set(),
                    calls=set(),
                    called_by=set(),
                    symbols_used=set()
                )
                self.functions[func_name] = current_function

    def get_function_code(self, function_name: str) -> Optional[str]:
        """関数のコードブロックを取得"""
        function = self.functions.get(function_name)
        if not function:
            return None
        
        lines = self.files[function.location.file]
        return ''.join(lines[function.location.start_line:function.location.end_line + 1])

# コード解析エンジン
class CodeAnalyzer:
    def __init__(self, codebase: CodebaseManager):
        self.codebase = codebase
        
    def analyze_register_usage(self, function_name: str) -> RegisterContext:
        """関数内のレジスタ使用状況を解析"""
        function = self.codebase.functions.get(function_name)
        if not function:
            return RegisterContext(set(), set(), set(), set())
        
        input_regs = set()
        output_regs = set()
        preserved_regs = set()
        modified_regs = set()
        
        file_lines = self.codebase.files[function.location.file]
        for i in range(function.location.start_line, function.location.end_line + 1):
            line = file_lines[i]
            self._analyze_register_patterns(line, input_regs, output_regs, preserved_regs, modified_regs)
            
        return RegisterContext(input_regs, output_regs, preserved_regs, modified_regs)

    def _analyze_register_patterns(self, line: str, input_regs: Set[str], 
                                 output_regs: Set[str], preserved_regs: Set[str], 
                                 modified_regs: Set[str]):
        """1行のコードからレジスタ使用パターンを検出"""
        # MOV命令の解析
        if mov_match := re.search(r'MOV\s+(\w+),\s*(\w+)', line):
            dst, src = mov_match.groups()
            if self._is_register(dst):
                modified_regs.add(dst)
            if self._is_register(src):
                input_regs.add(src)

        # PUSH/POP命令の解析
        if push_match := re.search(r'PUSH\.L\s+([R\d,-]+)', line):
            regs = self._parse_register_list(push_match.group(1))
            preserved_regs.update(regs)

    def _is_register(self, operand: str) -> bool:
        """オペランドがレジスタかどうかを判定"""
        return bool(re.match(r'R\d+|SP|PC', operand))

    def _parse_register_list(self, reg_list: str) -> Set[str]:
        """レジスタリストをパース（例: R6-R8 → {R6, R7, R8}）"""
        registers = set()
        for part in reg_list.split(','):
            if '-' in part:
                start, end = part.split('-')
                start_num = int(start.strip('R'))
                end_num = int(end.strip('R'))
                registers.update(f'R{i}' for i in range(start_num, end_num + 1))
            else:
                registers.add(part.strip())
        return registers

# コンテキスト抽出器
class ContextExtractor:
    def __init__(self, analyzer: CodeAnalyzer):
        self.analyzer = analyzer
        
    def extract_context(self, target_function: str, modification_type: str) -> FunctionContext:
        """修正に必要なコンテキストを抽出"""
        function = self.analyzer.codebase.functions.get(target_function)
        if not function:
            return None
        
        code_block = self.analyzer.codebase.get_function_code(target_function)
        register_usage = self.analyzer.analyze_register_usage(target_function)
        
        return FunctionContext(
            name=target_function,
            code_block=code_block,
            register_usage=register_usage,
            calls=list(function.calls),
            called_by=list(function.called_by),
            stack_usage=self._calculate_stack_usage(code_block)
        )

    def _calculate_stack_usage(self, code_block: str) -> int:
        """スタック使用量を計算"""
        # 簡略化した実装
        stack_usage = 0
        for line in code_block.splitlines():
            if 'PUSH' in line:
                stack_usage += 4  # 32ビットレジスタを想定
        return stack_usage

# プロンプト生成器
class PromptGenerator:
    def __init__(self):
        self.rx_registers = {
            'general': ['R1', 'R2', 'R3', 'R4', 'R5', 'R6', 'R7', 'R8', 'R9', 
                       'R10', 'R11', 'R12', 'R13', 'R14', 'R15'],
            'special': ['SP', 'PC', 'PSW'],
            'arg_regs': ['R1', 'R2', 'R3', 'R4'],
            'return_reg': 'R1',
            'preserved': ['R6', 'R7', 'R8', 'R9', 'R10', 'R11', 'R12', 'R13', 'R14', 'R15']
        }

    def generate_prompt(self, target_function: str, modification: str, 
                       context: FunctionContext) -> str:
        """コンテキストを考慮したプロンプトを生成"""
        modification_analysis = self._analyze_modification_type(modification)
        
        return f"""
# RXアセンブリコード修正プロンプト

## 対象関数: {target_function}

## 修正要件:
{modification}

## 現在のコンテキスト:
{self._format_register_usage(context.register_usage)}

{self._format_function_calls(context.calls, context.called_by)}

## 既存のコードブロック:
```asm
{context.code_block}
```

## スタック使用状況:
- 現在のスタック使用量: {context.stack_usage} bytes

{self._generate_code_guidelines(modification_analysis)}

## 生成規則:
1. RXアーキテクチャの命令セットに準拠
2. 既存のコーディングスタイルを維持
3. レジスタ使用規則:
   - R1: 戻り値用
   - R2-R4: 引数渡し用
   - R6-R15: 保存レジスタ（使用時は退避/復帰必須）

4. 関数呼び出し規約:
   - スタックフレームの適切な設定
   - 必要なレジスタの退避/復帰
   - アライメント要件の遵守

5. エラー処理:
   - 異常系の考慮
   - 適切なエラー値の設定
"""

    def _analyze_modification_type(self, modification: str) -> Dict[str, bool]:
        """修正内容を分析"""
        return {
            'needs_branching': any(keyword in modification.lower() 
                                 for keyword in ['場合', 'なら', 'if', 'when', '比較']),
            'needs_loop': any(keyword in modification.lower() 
                            for keyword in ['繰り返し', 'ループ', 'while', 'for', '回']),
            'modifies_registers': any(keyword in modification 
                                    for keyword in self.rx_registers['general']),
            'accesses_memory': any(keyword in modification.lower() 
                                 for keyword in ['メモリ', 'アドレス', '[', ']']),
        }

    def _format_register_usage(self, reg_context: RegisterContext) -> str:
        """レジスタ使用状況をフォーマット"""
        return f"""
レジスタ使用状況:
- 入力レジスタ: {', '.join(sorted(reg_context.input_regs))}
- 出力レジスタ: {', '.join(sorted(reg_context.output_regs))}
- 保存が必要なレジスタ: {', '.join(sorted(reg_context.preserved_regs))}
- 修正されるレジスタ: {', '.join(sorted(reg_context.modified_regs))}
"""

    def _format_function_calls(self, calls: List[str], called_by: List[str]) -> str:
        """関数呼び出し関係をフォーマット"""
        return f"""
関数呼び出し関係:
- 呼び出す関数: {', '.join(calls) if calls else 'なし'}
- 呼び出される関数: {', '.join(called_by) if called_by else 'なし'}
"""

    def _generate_code_guidelines(self, modification_analysis: Dict[str, bool]) -> str:
        """修正タイプに基づいたコードガイドラインを生成"""
        guidelines = ["## コード生成ガイドライン:"]
        
        if modification_analysis['needs_branching']:
            guidelines.append("""
- 分岐命令の使用:
  * CMP命令で比較を行う
  * 適切な条件分岐命令を使用
  * 分岐先のラベルは既存の命名規則に従う""")
            
        if modification_analysis['modifies_registers']:
            guidelines.append("""
- レジスタ操作:
  * 使用前のレジスタ値は必要に応じてスタックに退避
  * 関数終了時に保存レジスタを復帰
  * R1は戻り値用レジスタとして使用""")
            
        if modification_analysis['accesses_memory']:
            guidelines.append("""
- メモリアクセス:
  * アライメント要件を考慮
  * 適切なアドレッシングモードを使用
  * 必要に応じてメモリバリア命令を使用""")
            
        return "\n".join(guidelines)

# コード生成・検証システム
class CodeGenerator:
    def __init__(self, prompt_generator: PromptGenerator):
        self.prompt_generator = prompt_generator
        
    def generate_code(self, target_function: str, modification: str, 
                     context: FunctionContext) -> str:
        """AIを使用してコードを生成"""
        prompt = self.prompt_generator.generate_prompt(
            target_function, modification, context)
        
        # ここでAIモデルを呼び出してコードを生成
        # generated_code = ai_model.generate(prompt)
        
        # 生成されたコードの検証
        # self._verify_code(generated_code, context)
        
        return "generated_code"  # 実際のAI生成コード

    def _verify_code(self, generated_code: str, context: FunctionContext) -> bool:
        """生成されたコードの検証"""
        # レジスタ使用の検証
        # スタックフレームの検証
        # 分岐処理の検証
        # など
        pass

# メイン処理
def main():
    # システムの初期化
    codebase = CodebaseManager()
    analyzer = CodeAnalyzer(codebase)
    extractor = ContextExtractor(analyzer)
    generator = CodeGenerator(PromptGenerator())
    
    # ソースコードの読み込み
    codebase.load_file("path/to/source.asm")
    
    # ユーザーからの入力
    target_function = "FUNC_A"
    modification = "R2の値が0より小さい場合はR1に-1を設定して返す"
    
    # コンテキストの抽出
    context = extractor.extract_context(target_function, "modification")
    
    # コード生成
    new_code = generator.generate_code(target_function, modification, context)
    
    print("生成されたコード:")
    print(new_code)

if __name__ == "__main__":
    main()
