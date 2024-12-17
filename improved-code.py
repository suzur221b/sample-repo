from dataclasses import dataclass
from typing import Dict, List, Set, Optional, Tuple
import re
import logging
from datetime import datetime

# 既存のデータ構造とクラスは維持
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

# 既存のクラスはそのまま維持（CodebaseManager, CodeAnalyzer, ContextExtractor）

# プロンプト生成器に改善を追加
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
        
    def generate_review_prompt(self, code: str, context: FunctionContext) -> str:
        """レビュー用のプロンプトを生成"""
        return f"""
# コードレビュー依頼

## 対象コード:
```asm
{code}
```

## 現在のコンテキスト:
{self._format_context(context)}

## レビュー観点:
1. 機能的な正確性
   - 仕様との整合性
   - エッジケースの処理
   - 条件分岐の実装

2. 安全性
   - レジスタの保存/復元
   - スタックの使用
   - 例外処理

3. パフォーマンス
   - 不要な命令の有無
   - レジスタ割り当ての最適性
   - 分岐予測への配慮

4. 保守性
   - コードの可読性
   - 命名規則の遵守
   - コメントの適切さ

## フィードバック形式:
- 各観点について問題点を指摘
- 具体的な改善提案を提示
- コードの修正例を提示（必要な場合）

このコードについて、考えられる問題点や改善案を詳細に示してください。
"""

    def _format_context(self, context: FunctionContext) -> str:
        return f"""
- 関数名: {context.name}
- レジスタ使用状況:
  * 入力: {', '.join(context.register_usage.input_regs)}
  * 出力: {', '.join(context.register_usage.output_regs)}
  * 保存: {', '.join(context.register_usage.preserved_regs)}
- スタック使用量: {context.stack_usage} bytes
- 呼び出し関係:
  * 呼び出す関数: {', '.join(context.calls)}
  * 呼び出される関数: {', '.join(context.called_by)}
"""

# コード生成・検証システムを拡張
class CodeGenerator:
    def __init__(self, prompt_generator: PromptGenerator):
        self.prompt_generator = prompt_generator
        self.feedback_history: List[Dict] = []
        
    def generate_code_with_feedback(self, target_function: str, modification: str, 
                                  context: FunctionContext, max_iterations: int = 3) -> str:
        """フィードバックループを使用してコードを生成・改善"""
        current_code = None
        
        for iteration in range(max_iterations):
            # コード生成
            prompt = self.prompt_generator.generate_prompt(
                target_function, modification, context)
            if current_code:
                prompt += f"\n\n前回の生成コードと改善点:\n```asm\n{current_code}\n```"
            
            new_code = self._generate_code(prompt)
            
            # レビュー実行
            review_prompt = self.prompt_generator.generate_review_prompt(new_code, context)
            review_result = self._get_code_review(review_prompt)
            
            # 結果を記録
            self.feedback_history.append({
                'iteration': iteration + 1,
                'code': new_code,
                'review': review_result,
                'timestamp': datetime.now()
            })
            
            # レビュー結果が良好な場合は終了
            if self._is_code_acceptable(review_result):
                return new_code
                
            current_code = new_code
            modification = self._update_modification_based_on_review(
                modification, review_result)
        
        # 最後の生成コードを返す
        return current_code

    def _generate_code(self, prompt: str) -> str:
        """AIモデルを使用してコードを生成"""
        # ここでLLM APIを呼び出してコードを生成
        # 実際の実装ではAI modelのAPIを使用
        return "generated_code"

    def _get_code_review(self, review_prompt: str) -> Dict:
        """AIモデルを使用してコードレビューを実行"""
        # ここでLLM APIを呼び出してレビューを取得
        # 実際の実装ではAI modelのAPIを使用
        return {
            'issues': [],
            'suggestions': [],
            'is_acceptable': True
        }

    def _is_code_acceptable(self, review_result: Dict) -> bool:
        """レビュー結果からコードの受入可否を判定"""
        return (review_result['is_acceptable'] and 
                not review_result['issues'])

    def _update_modification_based_on_review(self, original_modification: str, 
                                           review_result: Dict) -> str:
        """レビュー結果に基づいて修正要件を更新"""
        updated_modification = original_modification + "\n\n改善点:"
        for suggestion in review_result['suggestions']:
            updated_modification += f"\n- {suggestion}"
        return updated_modification

    def get_feedback_history(self) -> List[Dict]:
        """フィードバック履歴を取得"""
        return self.feedback_history

def main():
    # システムの初期化
    codebase = CodebaseManager()
    analyzer = CodeAnalyzer(codebase)
    extractor = ContextExtractor(analyzer)
    generator = CodeGenerator(PromptGenerator())
    
    # ソースコードの読み込み
    codebase.load_file("path/to/source.asm")
    
    # 対象関数とモディフィケーション
    target_function = "FUNC_A"
    modification = "R2の値が0より小さい場合はR1に-1を設定して返す"
    
    # コンテキストの抽出
    context = extractor.extract_context(target_function, "modification")
    
    # フィードバックループを使用してコード生成
    final_code = generator.generate_code_with_feedback(
        target_function, modification, context)
    
    print("生成されたコード:")
    print(final_code)
    
    # フィードバック履歴の表示
    print("\n改善履歴:")
    for feedback in generator.get_feedback_history():
        print(f"\nIteration {feedback['iteration']} "
              f"({feedback['timestamp'].strftime('%Y-%m-%d %H:%M:%S')})")
        print(f"生成されたコード:\n{feedback['review']}")

if __name__ == "__main__":
    main()
