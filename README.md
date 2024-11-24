import * as vscode from 'vscode';
import axios from 'axios';

export function activate(context: vscode.ExtensionContext) {
  console.log('Your extension "codeGenerator" is now active!');

  let disposable = vscode.commands.registerCommand('codegenerator.generateFromComment', async () => {
    // APIキーを取得
    const configuration = vscode.workspace.getConfiguration('codegenerator');
    const apiKey = configuration.get('apiKey');
    if (!apiKey) {
      vscode.window.showInformationMessage("APIKeyが設定されていません。拡張機能からAPI Keyを設定してください。");
      return;
    }

    const editor = vscode.window.activeTextEditor;
    if (!editor) {
      vscode.window.showInformationMessage("アクティブなエディターが見つかりません。");
      return;
    }

    const document = editor.document;
    const selection = editor.selection;
    const text = document.getText(selection);

    // 選択範囲がない場合、カーソル行のコメントを使用
    const cursorPosition = editor.selection.active.line;
    const cursorLineText = document.lineAt(cursorPosition).text.trim();

    let commentContent = text || cursorLineText;

    if (!commentContent.startsWith('//') && !commentContent.startsWith('#')) {
      vscode.window.showInformationMessage('コメントを選択するか、カーソルをコメント行に置いてください。');
      return;
    }

    // コメントからコード生成のリクエストを作成
    const prompt = `以下のコメントを基に適切なコードを生成してください。生成するコードはコメントに関連するものにしてください。\nコメント: ${commentContent}`;

    const apiEndpoint = "https://api.openai.com/v1/chat/completions";
    try {
      vscode.window.showInformationMessage('AIによるコード生成を実行中です...');

      const requestBody = {
        "model": "gpt-3.5-turbo",
        "messages": [{
          "role": "user",
          "content": prompt
        }],
        "temperature": 0.7
      };

      const headers = {
        Authorization: `Bearer ${apiKey}`,
        "Content-Type": "application/json"
      };

      const response = await axios.post(apiEndpoint, requestBody, { headers });
      const generatedCode = response.data.choices[0].message.content;

      // ファイルの拡張子から言語を判定
      const language = detectLanguageFromFileExtension(document.fileName) || 'plaintext';
      const previewDocument = await vscode.workspace.openTextDocument({
        language,
        content: `// --- AI Generated Code Preview ---\n${generatedCode}`
      });
      await vscode.window.showTextDocument(previewDocument, { preview: true });

      // 確認ダイアログ
      const userChoice = await vscode.window.showInformationMessage(
        '生成されたコードを挿入しますか？',
        { modal: true },
        '挿入', 'キャンセル'
      );

      if (userChoice === '挿入') {
        // エディターに生成されたコードを挿入
        editor.edit(editBuilder => {
          const insertPosition = new vscode.Position(cursorPosition + 1, 0);
          editBuilder.insert(
            insertPosition,
            `\n// --- AI Generated Code START ---\n${generatedCode}\n// --- AI Generated Code END ---\n`
          );
        });
        vscode.window.showInformationMessage('コードが挿入されました。');
      } else {
        vscode.window.showInformationMessage('コードの挿入がキャンセルされました。');
      }
    } catch (error) {
      console.error(error);
      vscode.window.showErrorMessage('コード生成中にエラーが発生しました。APIキーやインターネット接続を確認してください。');
    }
  });

  context.subscriptions.push(disposable);
}

export function deactivate() {}

/**
 * ファイルの拡張子からプログラミング言語を判定する関数
 * @param fileName ファイル名
 * @returns 判定された言語名（例: "javascript", "python"）
 */
function detectLanguageFromFileExtension(fileName: string): string | undefined {
  const extension = fileName.split('.').pop()?.toLowerCase();
  switch (extension) {
    case 'js':
      return 'javascript';
    case 'ts':
      return 'typescript';
    case 'py':
      return 'python';
    case 'java':
      return 'java';
    case 'cs':
      return 'csharp';
    case 'html':
      return 'html';
    case 'css':
      return 'css';
    case 'json':
      return 'json';
    case 'xml':
      return 'xml';
    case 'sh':
      return 'shellscript';
    case 'php':
      return 'php';
    case 'rb':
      return 'ruby';
    case 'go':
      return 'go';
    default:
      return undefined; // 該当なし
  }
}
