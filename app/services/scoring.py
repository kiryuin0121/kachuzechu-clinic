"""採点ロジック

Whisper の認識結果とお題の furigana を比較して、正確さ・速さ・総合の3つを採点する。
"""

import re
import unicodedata
from difflib import SequenceMatcher
from typing import Dict, List

try:
    from pykakasi import kakasi
except Exception:
    # pykakasi が無い環境では漢字→ひらがな変換をせずに採点を続ける
    kakasi = None


def _convert_katakana_to_hiragana(text: str) -> str:
    """カタカナをひらがなに変換する"""
    normalized = unicodedata.normalize("NFKC", text)
    result = []

    for char in normalized:
        code_point = ord(char)
        # ァ〜ヴ（U+30A1〜U+30F4）は 0x60 引くと対応するひらがなになる
        if 0x30A1 <= code_point <= 0x30F4:
            result.append(chr(code_point - 0x60))
        else:
            result.append(char)

    return "".join(result)


def normalize_text(text: str) -> str:
    """認識結果・正解を比較用の全ひらがな文字列に整える"""
    if text is None:
        return ""

    text = unicodedata.normalize("NFKC", text)
    text = text.casefold()
    text = text.replace("　", " ")
    text = text.replace("\n", " ")

    # 句読点・記号を除去。Whisper がかぎ括弧や引用符を付けて返すことがあるので、それらも含める
    text = re.sub(r"[、。．，,.!?！？…・;:()（）\[\]{}<>「」『』\"'\-\_\+\=]", "", text)
    text = re.sub(r"\s+", "", text)

    # pykakasi の J→H 変換は漢字だけが対象でカタカナは残るため、
    # 「バナナ」のような外来語を「ばなな」に揃えるカタカナ変換を別途かける
    if kakasi is not None:
        converter = kakasi()
        converter.setMode("J", "H")
        text = converter.getConverter().do(text)

    text = _convert_katakana_to_hiragana(text)

    return text


def generate_diff(expected: str, actual: str) -> List[Dict[str, str]]:
    """正解と認識結果の差分を、画面で色分け表示しやすい区間リストにする"""
    matcher = SequenceMatcher(None, expected, actual)
    segments: List[Dict[str, str]] = []

    # type は equal / replace / insert / delete のいずれか
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        segments.append(
            {
                "type": tag,
                "expected": expected[i1:i2],
                "actual": actual[j1:j2],
            }
        )

    return segments


# 早口言葉は3回連続で言うルール。正解文字列はこの回数分繰り返して比較する。
# target_duration は3回分の合計時間として登録されているので、こちらは倍率をかけない。
PRACTICE_REPEAT_COUNT = 3


def score_tongue_twister(
    expected_furigana: str,
    transcribed_text: str,
    duration_seconds: float,
    target_duration: float,
    expected_phrase: str = ""
) -> Dict[str, object]:
    """早口言葉の発話を採点する

    引数:
        expected_furigana : お題の読み（ひらがな、1回分）
        transcribed_text  : Whisper の認識結果（3回分）
        duration_seconds  : 発話にかかった時間（3回分の合計、秒）
        target_duration   : 目標時間（3回分の合計、秒）
        expected_phrase   : お題本文（漢字かな混じり、1回分）。省略可

    戻り値: 採点結果の辞書。success=False のときは message に理由が入る
    """

    try:
        # フロントから来る値は文字列のこともあるので float に揃える
        duration_value = float(duration_seconds)
        target_value = float(target_duration)

        if duration_value <= 0 or target_value <= 0:
            return {"success": False, "message": "録音時間または目標時間が不正です。"}

        transcribed_hiragana = normalize_text(transcribed_text)

        # 正解候補は furigana と、phrase を pykakasi に通した読みの2つ。
        # Whisper は漢字で返すことが多く、その漢字を pykakasi で読むと
        # 「操縦中」→「そうじゅうなか」のように誤ることがある。
        # phrase も同じ変換器に通しておけば両側で同じ読みになるので、不当な減点を防げる。
        expected_candidates = [normalize_text(expected_furigana * PRACTICE_REPEAT_COUNT)]
        if expected_phrase:
            phrase_reading = normalize_text(expected_phrase * PRACTICE_REPEAT_COUNT)
            if phrase_reading and phrase_reading not in expected_candidates:
                expected_candidates.append(phrase_reading)

        expected_candidates = [candidate for candidate in expected_candidates if candidate]

        if not expected_candidates:
            return {"success": False, "message": "正解データが取得できませんでした。"}

        # 認識結果に近い方の候補を正解として使う
        expected_hiragana = max(
            expected_candidates,
            key=lambda candidate: SequenceMatcher(None, candidate, transcribed_hiragana).ratio(),
        )

        # 正確さ: 文字列の一致率をそのまま100点満点にする
        matcher = SequenceMatcher(None, expected_hiragana, transcribed_hiragana)
        accuracy_score = round(max(0.0, min(100.0, matcher.ratio() * 100)), 2)

        # 速さ: 1秒あたりの文字数を目標と比べ、ズレの割合だけ減点する（ズレ100%以上で0点）
        expected_chars = max(len(expected_hiragana), 1)
        target_chars_per_second = expected_chars / target_value
        observed_chars_per_second = len(transcribed_hiragana) / duration_value
        speed_gap = abs(observed_chars_per_second - target_chars_per_second) / max(target_chars_per_second, 1.0)
        speed_score = round(max(0.0, min(100.0, 100 * (1 - min(speed_gap, 1.0)))), 2)

        # 総合: 早口言葉なので正確さを重視し、正確さ7割・速さ3割で合算する
        total_score = round((accuracy_score * 0.7) + (speed_score * 0.3), 2)

        return {
            "success": True,
            "accuracy_score": accuracy_score,
            "speed_score": speed_score,
            "total_score": total_score,
            "transcribed_text": transcribed_text,          # Whisper の生の認識結果
            "transcribed_hiragana": transcribed_hiragana,  # 正規化後の認識結果
            "expected_hiragana": expected_hiragana,        # 正規化後の正解（3回分）
            "duration_seconds": duration_value,
            "target_duration": target_value,
            "repeat_count": PRACTICE_REPEAT_COUNT,
            "diff": generate_diff(expected_hiragana, transcribed_hiragana),
        }

    except Exception as exc:
        # 型変換の失敗などで落とさず、失敗として呼び出し元に返す
        return {"success": False, "message": f"採点処理に失敗しました: {exc}"}
