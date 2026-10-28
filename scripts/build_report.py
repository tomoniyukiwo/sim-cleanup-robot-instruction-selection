"""Build the editable report draft as a three-page Japanese PDF."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle

FIELDS = ['account', 'github_url', 'youtube_url', 'git_commit', 'result_note',
          'input_instruction', 'task', 'result', 'conditions', 'model_revisions', 'extra_checks']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--data', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--final', action='store_true')
    ap.add_argument('--font', type=Path, default=Path(__file__).resolve().parents[1] / 'submission/fonts/NotoSansJP-Regular.ttf')
    args = ap.parse_args()
    data = json.loads(args.data.read_text())
    missing = [k for k in FIELDS if not isinstance(data.get(k), str) or not data[k].strip()
               or '［' in data[k] or '記入' in data[k]]
    if args.final and (missing or data.get('is_final') is not True):
        ap.error(f'Complete fields and set is_final=true first: {missing}')
    if args.out.exists():
        ap.error('Output exists; choose a new --out')
    if not args.font.is_file():
        ap.error('Japanese TTF missing: supply --font /path/to/Japanese.ttf')
    font = 'ReportJapanese'
    pdfmetrics.registerFont(TTFont(font, str(args.font)))
    styles = {
        'title': ParagraphStyle('title', fontName=font, fontSize=21, leading=30, textColor=colors.HexColor('#12334B'), spaceAfter=14, wordWrap='CJK'),
        'h': ParagraphStyle('h', fontName=font, fontSize=12, leading=19, spaceBefore=12, spaceAfter=7, textColor=colors.HexColor('#126B76'), wordWrap='CJK'),
        'b': ParagraphStyle('b', fontName=font, fontSize=9.5, leading=16, spaceAfter=7, wordWrap='CJK'),
        's': ParagraphStyle('s', fontName=font, fontSize=8, leading=13, spaceAfter=6, wordWrap='CJK'),
    }
    story = []
    def p(text, kind='b'):
        return Paragraph(escape(str(text)).replace('\n', '<br/>'), styles[kind])
    def add(text, kind='b'):
        story.append(p(text, kind))
    status = '提出用説明資料' if args.final else '草稿 / 未記入項目を更新してから提出'
    add('Physical AI 応用1 / 最終課題', 's')
    add('ROS 2とローカルLLMで監視する\n片付けロボット', 'title')
    add(status, 'h')
    add('提出者：'+data['account'])
    add('GitHub：'+data['github_url'])
    add('YouTube：'+data['youtube_url'])
    add('1. 目的とタスク', 'h')
    add('自然言語の依頼を登録済みの物体操作タスクへ対応付け、シミュレーション内のロボットアームに実行させる。公開済み操作モデルに、指示選択とROSによる実行監視を組み合わせる。実機・外部推論API・独自の追加学習は使用しない。')
    add('2. システムの構成', 'h')
    rows = [('担当', '使用技術と役割'), ('指示解釈', 'Qwen3.5-2B：登録タスク選択・確認質問'), ('実行監視', 'ROS 2 Humble：指示・通知・停止／再開・再試行許可'), ('物体操作', 'SmolVLA LIBERO：画像・状態・指示から行動を推論'), ('物理・判定', 'LIBERO / MuJoCo：物理シミュレーションと目標条件')]
    table = Table([[p(a,'s'),p(b,'s')] for a,b in rows], colWidths=[82,405])
    table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#E6F1F4')),('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),9),('RIGHTPADDING',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),7),('LINEBELOW',(0,0),(-1,-1),0.3,colors.HexColor('#CFDDE3'))]))
    story.append(table)
    add('LLMはタスク一覧のテキストを読み、操作前に解放する。SmolVLAがカメラ画像を使う。成功はLLMの判断ではなく、LIBEROの目標述語で確認する。', 's')
    story.append(PageBreak())
    add('実装の工夫と実行記録', 'title')
    add('3. 自作した部分', 'h')
    for text in ['LLMのJSON出力を検査し、登録task_idだけを受け付ける。曖昧な依頼には確認質問を返す構成とした。', 'ROSのシステムPythonとAI用Python 3.12を別プロセスに分け、JSON行で通信する。操作境界で停止・再開・取消を扱う。', '予算内に目標未達の場合はROSの再試行許可を待つ。物体位置を初期化せず、操作キューを破棄して現在状態から再推論する。', 'モデルrevision・タスク・乱数・イベント・動画を保存し、説明と再現確認に利用する。']:
        add('・'+text)
    add('4. 実行環境', 'h')
    add('Ubuntu 22.04.5 LTS / RTX 4060 Ti（VRAM 16GB）/ ROS 2 Humble。AI用Python 3.12.12、LeRobot 0.4.4、torch 2.7.1+cu128、torchvision 0.22.1+cu128、transformers 4.57.6、hf-libero 0.1.4。依存はuv.lockで固定。')
    add('5. 結果と証拠', 'h')
    add(data['result_note'])
    for label,key in [('入力指示','input_instruction'),('選択タスク','task'),('目標判定','result'),('実行条件','conditions'),('モデルrevision','model_revisions'),('追加確認','extra_checks')]:
        add(label+'：'+data[key], 's')
    story.append(PageBreak())
    add('制約・出典と提出情報', 'title')
    add('6. 制約と考察', 'h')
    add('登録済みLIBEROタスクが対象であり、未知の物体や任意の片付けへの汎化は検証していない。LLMはカメラ画像を見ず、タスク選択の意味的な正しさは人が確認する必要がある。')
    add('再試行はオンライン学習や失敗原因の診断ではない。現在状態からの再推論であり、改善を保証しない。停止・再開・確認質問・再試行は実測した機能と未実施の機能を区別する。')
    add('実機での動作とVRAMピーク使用量は未計測。ROSを使用し、シミュレータはLIBERO/MuJoCoを使用した。Gazebo/Genesisは使用していない。動画がシミュレーション時間基準であること、待ち時間の省略や再生速度を説明する。')
    add('7. 外部資源と独自部分の区別', 'h')
    add('Qwen・SmolVLA・LeRobot・LIBERO・ROS 2・MuJoCoを利用した。操作モデルの学習や物理エンジン自体は独自開発ではない。独自部分は指示の選択・検査、ROS監視とプロセス間通信、再試行制御、実行記録と提出用整理である。')
    add('コード・資料の作成とデバッグにChatGPT/Codexを利用。受講者が内容を確認して実行・評価する。モデル重みは再配布せず、元の配布元を参照する。')
    add('参考URL', 'h')
    for link in ['https://huggingface.co/Qwen/Qwen3.5-2B','https://huggingface.co/lerobot/smolvla_libero','https://github.com/huggingface/lerobot/tree/v0.4.4','https://github.com/Lifelong-Robot-Learning/LIBERO','https://docs.ros.org/en/humble/','https://github.com/google-deepmind/mujoco']:
        add(link,'s')
    add('提出時点のGit commit：'+data['git_commit'], 's')
    add('PDF名：説明資料_PAI最終課題_omnicampusアカウント名.pdf', 's')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    doc = SimpleDocTemplate(str(args.out), pagesize=A4, leftMargin=54, rightMargin=54, topMargin=44, bottomMargin=42, title='ROS 2とローカルLLMで監視する片付けロボット',author='Physical AI 最終課題')
    def footer(canvas,doc):
        canvas.setFont(font,8);canvas.setFillColor(colors.HexColor('#596B78'))
        canvas.drawString(54,25,status)
        canvas.drawRightString(A4[0]-54,25,str(doc.page))
    doc.build(story,onFirstPage=footer,onLaterPages=footer)
    print(f'Saved {args.out}; inspect the PDF before submitting.')


if __name__ == '__main__':
    main()
