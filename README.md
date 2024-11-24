# sample-repo
new-text

import * as vscode from 'vscode';
import axios from 'axios';

interface CodeGeneratorConfig {
  apiKey: string;
  model: string;
  temperature: number;
  language: string;
  insertTemplate: boolean;
  maxTokens: number;
}

export function activate(context: vscode.ExtensionContext) {
  console.log('Your extension "codeGenerator" is now active!');

  // コマンドの登録
  let disposables = [
    vscode.commands.registerCommand('codegenerator.generateFromComment', handleCodeGeneration),
    vscode.commands.registerCommand('codegenerator.configureSettings', showConfigurationUI),
    vscode.commands.registerCommand('codegenerator.generateWithTemplate', () => handleCodeGeneration(true))
  ];

  context.subscriptions.push(...disposables);
}

async function getConfiguration(): Promise<CodeGeneratorConfig> {
  const config = vscode.workspace.getConfiguration('codegenerator');
  return {
    apiKey: config.get('apiKey') || '',
    model: config.get('model') || 'gpt-3.5-turbo',
    temperature: config.get('temperature') || 0.7,
    language: config.get('defaultLanguage') || 'auto',
    insertTemplate: config.get('insertTemplate') || false,
    maxTokens: config.get('maxTokens') || 2000
  };
}

async function showConfigurationUI() {
  const config = await getConfiguration();
  const items = [
    {
      label: 'Set API Key',
      description: 'Configure OpenAI API Key'
    },
    {
      label: 'Select Model',
      description: `Current: ${config.model}`
    },
    {
      label: 'Set Temperature',
      description: `Current: ${config.temperature}`
    },
    {
      label: 'Set Default Language',
      description: `Current: ${config.language}`
    }
  ];

  const selection = await vscode.window.showQuickPick(items, {
    placeHolder: 'Select setting to configure'
  });

  if (!selection) return;

  switch (selection.label) {
    case 'Set API Key':
      const apiKey = await vscode.window.showInputBox({
        prompt: 'Enter your OpenAI API Key',
        password: true
      });
      if (apiKey) {
        await vscode.workspace.getConfiguration().update('codegenerator.apiKey', apiKey, true);
      }
      break;
    case 'Select Model':
      const models = ['gpt-3.5-turbo', 'gpt-4'];
      const model = await vscode.window.showQuickPick(models, {
        placeHolder: 'Select AI model'
      });
      if (model) {
        await vscode.workspace.getConfiguration().update('codegenerator.model', model, true);
      }
      break;
    // 他の設定オプションも同様に実装
  }
}

async function handleCodeGeneration(useTemplate: boolean = false) {
  const config = await getConfiguration();
  const editor = vscode.window.activeTextEditor;
  
  if (!editor) {
    vscode.window.showInformationMessage("アクティブなエディターが見つかりません。");
    return;
  }

  if (!config.apiKey) {
    const result = await vscode.window.showErrorMessage(
      "APIKeyが設定されていません。設定しますか？",
      "はい",
      "いいえ"
    );
    if (result === "はい") {
      await showConfigurationUI();
    }
    return;
  }

  try {
    const codeContext = await getCodeContext(editor);
    const generatedCode = await generateCode(codeContext, config, useTemplate);
    await handleCodeInsertion(editor, generatedCode, config);
  } catch (error) {
    handleError(error);
  }
}

interface CodeContext {
  comment: string;
  surroundingCode: string;
  language: string;
}

async function getCodeContext(editor: vscode.TextEditor): Promise<CodeContext> {
  const document = editor.document;
  const selection = editor.selection;
  const cursorPosition = selection.active.line;

  // 選択されたテキストまたはカーソル行のコメントを取得
  let commentContent = document.getText(selection) || document.lineAt(cursorPosition).text.trim();

  // 周辺のコードコンテキストを取得（カーソルの前後5行）
  const startLine = Math.max(0, cursorPosition - 5);
  const endLine = Math.min(document.lineCount - 1, cursorPosition + 5);
  const surroundingCode = document.getText(new vscode.Range(startLine, 0, endLine, document.lineAt(endLine).text.length));

  // 言語検出
  const language = detectLanguageFromFileExtension(document.fileName) || 'plaintext';

  if (!commentContent.startsWith('//') && !commentContent.startsWith('#')) {
    throw new Error('コメントを選択するか、カーソルをコメント行に置いてください。');
  }

  return {
    comment: commentContent,
    surroundingCode,
    language
  };
}

async function generateCode(
  context: CodeContext,
  config: CodeGeneratorConfig,
  useTemplate: boolean
): Promise<string> {
  const prompt = createPrompt(context, useTemplate);
  
  const requestBody = {
    model: config.model,
    messages: [{
      role: "user",
      content: prompt
    }],
    temperature: config.temperature,
    max_tokens: config.maxTokens
  };

  const response = await axios.post(
    "https://api.openai.com/v1/chat/completions",
    requestBody,
    {
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        "Content-Type": "application/json"
      }
    }
  );

  return response.data.choices[0].message.content;
}

function createPrompt(context: CodeContext, useTemplate: boolean): string {
  let prompt = `以下のコメントを基に${context.language}のコードを生成してください。
コメント: ${context.comment}

現在のコンテキスト:
${context.surroundingCode}

要件:
- ${context.language}の最新のベストプラクティスに従ってください
- エラーハンドリングを適切に実装してください
- コードにはドキュメンテーションコメントを含めてください
`;

  if (useTemplate) {
    prompt += `
テンプレートとして以下の要素を含めてください：
- 関数のインターフェース定義
- 入力バリデーション
- エラーハンドリング
- ユニットテストのサンプル
- 使用例
`;
  }

  return prompt;
}

async function handleCodeInsertion(
  editor: vscode.TextEditor,
  generatedCode: string,
  config: CodeGeneratorConfig
) {
  // プレビューを表示
  const previewDocument = await vscode.workspace.openTextDocument({
    language: editor.document.languageId,
    content: `// --- AI Generated Code Preview ---\n${generatedCode}`
  });
  await vscode.window.showTextDocument(previewDocument, { preview: true, viewColumn: vscode.ViewColumn.Beside });

  // 確認ダイアログ
  const userChoice = await vscode.window.showInformationMessage(
    '生成されたコードを挿入しますか？',
    { modal: true },
    '挿入', '修正して挿入', 'キャンセル'
  );

  if (userChoice === '挿入' || userChoice === '修正して挿入') {
    let codeToInsert = generatedCode;
    
    if (userChoice === '修正して挿入') {
      const editedCode = await vscode.window.showInputBox({
        prompt: 'コードを編集してください',
        value: generatedCode,
        multiline: true
      });
      if (!editedCode) return;
      codeToInsert = editedCode;
    }

    await editor.edit(editBuilder => {
      const insertPosition = new vscode.Position(editor.selection.active.line + 1, 0);
      editBuilder.insert(
        insertPosition,
        `\n// --- AI Generated Code START ---\n${codeToInsert}\n// --- AI Generated Code END ---\n`
      );
    });

    vscode.window.showInformationMessage('コードが挿入されました。');
  }
}

function handleError(error: any) {
  console.error(error);
  const errorMessage = error.response?.data?.error?.message || error.message || '不明なエラーが発生しました';
  vscode.window.showErrorMessage(`エラー: ${errorMessage}`);
}

// 既存のdetectLanguageFromFileExtension関数はそのまま維持

export function deactivate() {}