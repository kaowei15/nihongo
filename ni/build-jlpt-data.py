# -*- coding: utf-8 -*-
"""Build nihongo-n5.js and nihongo-n4.js from JLPT CSV word lists."""
import csv
import json
import re
import time
from pathlib import Path

try:
    from deep_translator import GoogleTranslator
    HAS_TRANSLATOR = True
except ImportError:
    HAS_TRANSLATOR = False

BASE = Path(__file__).parent
CACHE_FILE = BASE / "translation-cache.json"

N5_GRAMMAR = [
    {"title": "です / だ — 斷定", "pattern": "名詞 + です", "example": "私は学生です。", "exampleZh": "我是學生。", "note": "禮貌斷定句尾。だ 為普通體。"},
    {"title": "は — 主題標記", "pattern": "A は B", "example": "私は日本人です。", "exampleZh": "我是日本人。", "note": "讀作 wa，標示句子主題。"},
    {"title": "が — 主語標記", "pattern": "A が B", "example": "雨が降っています。", "exampleZh": "正在下雨。", "note": "標示自然現象、能力、好惡的主語。"},
    {"title": "を — 賓語標記", "pattern": "名詞 + を + 動詞", "example": "水を飲みます。", "exampleZh": "喝水。", "note": "讀作 o，標示動作對象。"},
    {"title": "に — 時間・方向・存在", "pattern": "時間/場所 + に", "example": "七時に起きます。", "exampleZh": "七點起床。", "note": "時間點、存在場所、方向。"},
    {"title": "で — 場所・手段", "pattern": "場所/手段 + で", "example": "図書館で勉強します。", "exampleZh": "在圖書館讀書。", "note": "動作發生的場所或手段。"},
    {"title": "と — 和・一起", "pattern": "A と B", "example": "友達と映画を見ます。", "exampleZh": "和朋友看電影。", "note": "並列或共同動作對象。"},
    {"title": "から — 從・因為", "pattern": "A から B", "example": "九時から始まります。", "exampleZh": "從九點開始。", "note": "起點或原因（口語）。"},
    {"title": "まで — 到・直到", "pattern": "A まで B", "example": "五時まで働きます。", "exampleZh": "工作到五點。", "note": "終點、範圍上限。"},
    {"title": "へ — 朝向", "pattern": "名詞 + へ", "example": "日本へ行きます。", "exampleZh": "去日本。", "note": "讀作 e，表示方向。"},
    {"title": "の — 所有・修飾", "pattern": "A の B", "example": "私の本です。", "exampleZh": "是我的書。", "note": "所有、修飾、名詞化。"},
    {"title": "も — 也", "pattern": "名詞 + も", "example": "私も行きます。", "exampleZh": "我也去。", "note": "添加同類事物。"},
    {"title": "か — 疑問", "pattern": "～か", "example": "これは何ですか。", "exampleZh": "這是什麼？", "note": "一般疑問句句尾。"},
    {"title": "ね / よ — 語氣", "pattern": "句尾 + ね/よ", "example": "いい天気ですね。", "exampleZh": "天氣真好呢。", "note": "ね 尋求同意，よ 強調告知。"},
    {"title": "あります / います", "pattern": "場所 に もの/人 が ある/いる", "example": "机の上に本があります。", "exampleZh": "桌上有書。", "note": "存在句，いる 用於有生命。"},
    {"title": "ます形 — 禮貌動詞", "pattern": "動詞ます形", "example": "毎日勉強します。", "exampleZh": "每天讀書。", "note": "動詞禮貌肯定現在。"},
    {"title": "ません — 否定", "pattern": "動詞ません", "example": "今日は行きません。", "exampleZh": "今天不去。", "note": "ます形否定。"},
    {"title": "ました — 過去", "pattern": "動詞ました", "example": "昨日映画を見ました。", "exampleZh": "昨天看了電影。", "note": "ます形過去肯定。"},
    {"title": "ませんでした — 過去否定", "pattern": "動詞ませんでした", "example": "宿題をしませんでした。", "exampleZh": "沒做作業。", "note": "ます形過去否定。"},
    {"title": "て形 — 連接", "pattern": "動詞て形", "example": "食べて、飲みます。", "exampleZh": "吃了，然後喝。", "note": "連接動作、請求、進行等基礎。"},
    {"title": "てください — 請求", "pattern": "動詞て形 + ください", "example": "座ってください。", "exampleZh": "請坐。", "note": "禮貌請對方做某事。"},
    {"title": "ています — 進行・狀態", "pattern": "動詞て形 + います", "example": "今、勉強しています。", "exampleZh": "現在正在讀書。", "note": "動作進行或結果狀態。"},
    {"title": "たい — 想要", "pattern": "動詞ます形 + たい", "example": "日本に行きたいです。", "exampleZh": "想去日本。", "note": "表達第一人称願望。"},
    {"title": "ませんか — 邀請", "pattern": "動詞ませんか", "example": "一緒に食べませんか。", "exampleZh": "一起吃飯好嗎？", "note": "否定疑問邀請。"},
    {"title": "ましょう — 提議", "pattern": "動詞ましょう", "example": "休みましょう。", "exampleZh": "休息吧。", "note": "一起做的提議。"},
    {"title": "ないでください — 請不要", "pattern": "動詞ないで + ください", "example": "ここで写真を撮らないでください。", "exampleZh": "請不要在這裡拍照。", "note": "禁止請求。"},
    {"title": "なければならない — 必須", "pattern": "動詞ない形 + ければならない", "example": "薬を飲まなければなりません。", "exampleZh": "必須吃藥。", "note": "義務、必須。"},
    {"title": "ほうがいい — 最好", "pattern": "た形/ない形 + ほうがいい", "example": "早く寝たほうがいいです。", "exampleZh": "最好早點睡。", "note": "建議。"},
    {"title": "ので — 因為（客氣）", "pattern": "動詞/形容詞 + ので", "example": "雨なので、行きません。", "exampleZh": "因為下雨，不去。", "note": "說明原因，比 から 客氣。"},
    {"title": "が好き / が上手", "pattern": "名詞 + が好き/上手", "example": "音楽が好きです。", "exampleZh": "喜歡音樂。", "note": "好惡與擅長的表達。"},
    {"title": "ことができる — 能夠", "pattern": "動詞辞書形 + ことができる", "example": "日本語を話すことができます。", "exampleZh": "會說日語。", "note": "可能、能力。"},
    {"title": "前に / 後で — 之前之後", "pattern": "動詞辞書形 + 前に/後で", "example": "食事の後で散歩します。", "exampleZh": "飯後散步。", "note": "時間先後關係。"},
    {"title": "あまり〜ない — 不太", "pattern": "あまり + 否定", "example": "あまり食べません。", "exampleZh": "不太吃。", "note": "程度低，接否定。"},
    {"title": "い形容詞", "pattern": "い形容詞 + です", "example": "この映画は面白いです。", "exampleZh": "這部電影很有趣。", "note": "以 い 結尾的形容詞活用。"},
    {"title": "な形容詞", "pattern": "な形容詞 + です", "example": "この部屋は静かです。", "exampleZh": "這個房間很安靜。", "note": "な形容詞修飾名詞加 な。"},
    {"title": "こそあど — 指示詞", "pattern": "これ/それ/あれ/どれ", "example": "これは何ですか。", "exampleZh": "這是什麼？", "note": "這/那/哪系列指示詞。"},
    {"title": "疑問詞", "pattern": "何/どこ/いつ/だれ/どう", "example": "駅はどこですか。", "exampleZh": "車站在哪？", "note": "什麼、哪裡、何時、誰、如何。"},
    {"title": "より — 比較", "pattern": "A は B より ～", "example": "兄は私より背が高いです。", "exampleZh": "哥哥比我高。", "note": "比較對象。"},
    {"title": "一番 — 最", "pattern": "一番 + 形容詞", "example": "富士山が一番高いです。", "exampleZh": "富士山最高。", "note": "最高級。"},
    {"title": "でも — 即使・或者", "pattern": "名詞 + でも", "example": "お茶でも飲みませんか。", "exampleZh": "喝茶什麼的好嗎？", "note": "舉例、讓步。"},
    {"title": "毎〜 / 〜ごと", "pattern": "毎日/毎週/〜ごとに", "example": "毎日運動します。", "exampleZh": "每天運動。", "note": "頻率表達。"},
    {"title": "まだ / もう", "pattern": "まだ/もう + 動詞", "example": "もう食べました。", "exampleZh": "已經吃了。", "note": "還沒/已經。"},
    {"title": "だけ — 只有", "pattern": "名詞 + だけ", "example": "水だけ飲みます。", "exampleZh": "只喝水。", "note": "限定範圍。"},
    {"title": "しか〜ない — 只有（限定）", "pattern": "しか + 否定", "example": "百人しかいません。", "exampleZh": "只有一百人。", "note": "限定，帶否定。"},
]

N4_GRAMMAR = [
    {"title": "て形 + いる — 進行・狀態", "pattern": "動詞て形 + いる", "example": "今、本を読んでいます。", "exampleZh": "現在正在看書。", "note": "持續動作或狀態。"},
    {"title": "て形 + ある — 結果狀態", "pattern": "動詞て形 + ある", "example": "窓が開けてあります。", "exampleZh": "窗戶開著。", "note": "故意保持的狀態（他動詞）。"},
    {"title": "て形 + おく — 預先做", "pattern": "動詞て形 + おく", "example": "資料を読んでおきます。", "exampleZh": "先把資料讀完。", "note": "預先準備。"},
    {"title": "て形 + しまう — 完了・遺憾", "pattern": "動詞て形 + しまう", "example": "食べてしまいました。", "exampleZh": "不小心吃完了。", "note": "完了或遺憾語氣。"},
    {"title": "て形 + みる — 試試看", "pattern": "動詞て形 + みる", "example": "着てみます。", "exampleZh": "試穿看看。", "note": "嘗試做某事。"},
    {"title": "たことがある — 曾經", "pattern": "動詞た形 + ことがある", "example": "日本に行ったことがあります。", "exampleZh": "曾經去過日本。", "note": "過去經驗。"},
    {"title": "たほうがいい — 最好（過去形）", "pattern": "動詞た形 + ほうがいい", "example": "医者に行ったほうがいいです。", "exampleZh": "最好去看醫生。", "note": "對他人的建議。"},
    {"title": "ないほうがいい — 最好不要", "pattern": "動詞ない形 + ほうがいい", "example": "無理をしないほうがいい。", "exampleZh": "最好不要勉強。", "note": "否定建議。"},
    {"title": "ながら — 一邊…一邊", "pattern": "動詞ます形 + ながら", "example": "音楽を聞きながら走ります。", "exampleZh": "一邊聽音樂一邊跑。", "note": "同時進行兩動作。"},
    {"title": "ている間に — 在…期間", "pattern": "ている間に", "example": "寝ている間に雨が降りました。", "exampleZh": "睡覺期間下雨了。", "note": "某狀態持續期間發生的事。"},
    {"title": "そうだ — 看起來（樣態）", "pattern": "ます形 + そうだ", "example": "美味しそうです。", "exampleZh": "看起來很好吃。", "note": "根據外觀判斷。"},
    {"title": "そうだ — 聽說（傳聞）", "pattern": "句 + そうだ", "example": "明日は雨だそうです。", "exampleZh": "聽說明天會下雨。", "note": "傳聞，前接普通形。"},
    {"title": "ようだ — 好像", "pattern": "名詞/形容詞 + ようだ", "example": "雨が降るようです。", "exampleZh": "好像要下雨了。", "note": "根據跡象推測。"},
    {"title": "らしい — 似乎・典型", "pattern": "普通形 + らしい", "example": "彼は学生らしい。", "exampleZh": "他好像是學生。", "note": "傳聞或典型特徵。"},
    {"title": "ば — 條件", "pattern": "動詞ば形", "example": "早く起きれば、間に合います。", "exampleZh": "如果早起就來得及。", "note": "一般條件。"},
    {"title": "たら — 條件・發現", "pattern": "動詞た形 + ら", "example": "家に帰ったら、電話してください。", "exampleZh": "回家後請打電話。", "note": "條件或時間先後。"},
    {"title": "と — 條件（自然結果）", "pattern": "動詞辞書形 + と", "example": "春になると、桜が咲きます。", "exampleZh": "一到春天櫻花就開。", "note": "自然、習慣性結果。"},
    {"title": "なら — 話題條件", "pattern": "名詞/普通形 + なら", "example": "日本なら、桜が有名です。", "exampleZh": "說到日本，櫻花很有名。", "note": "就…而言的條件。"},
    {"title": "ても — 即使", "pattern": "動詞て形 + も", "example": "雨が降っても行きます。", "exampleZh": "即使下雨也去。", "note": "讓步條件。"},
    {"title": "なくてはいけない — 必須", "pattern": "動詞ない形 + てはいけない", "example": "宿題をしなくてはいけません。", "exampleZh": "必須做作業。", "note": "義務。"},
    {"title": "てはいけない — 禁止", "pattern": "動詞て形 + はいけない", "example": "ここでタバコを吸ってはいけません。", "exampleZh": "禁止在這裡吸菸。", "note": "禁止。"},
    {"title": "てもいい — 可以", "pattern": "動詞て形 + もいい", "example": "入ってもいいですか。", "exampleZh": "可以進去嗎？", "note": "許可。"},
    {"title": "ことにする / ことになる", "pattern": "辞書形 + ことにする/なる", "example": "来年留学することにしました。", "exampleZh": "決定明年留學。", "note": "主觀決定/客觀決定。"},
    {"title": "ようにする — 努力做到", "pattern": "辞書形/ない形 + ようにする", "example": "毎日運動するようにしています。", "exampleZh": "努力每天運動。", "note": "養成習慣的努力。"},
    {"title": "ようになる — 變得能", "pattern": "辞書形 + ようになる", "example": "日本語が話せるようになりました。", "exampleZh": "變得會說日語了。", "note": "能力或狀態變化。"},
    {"title": "ために — 為了・因為", "pattern": "名詞/動詞 + ために", "example": "健康のために運動します。", "exampleZh": "為了健康而運動。", "note": "目的或原因。"},
    {"title": "のに — 雖然", "pattern": "普通形 + のに", "example": "忙しいのに、手伝ってくれました。", "exampleZh": "雖然很忙還是幫了我。", "note": "轉折，帶不滿。"},
    {"title": "し — 並列理由", "pattern": "普通形 + し", "example": "安いし、美味しいし。", "exampleZh": "又便宜又好吃。", "note": "列舉理由或並列。"},
    {"title": "ばかり — 剛剛・只", "pattern": "動詞て形 + ばかり", "example": "来たばかりです。", "exampleZh": "剛來。", "note": "剛完成或限定。"},
    {"title": "はずだ — 應該", "pattern": "普通形 + はずだ", "example": "彼はもう着いたはずです。", "exampleZh": "他應該已經到了。", "note": "根據邏輯的推斷。"},
    {"title": "べきだ — 應該（義務）", "pattern": "動詞辞書形 + べきだ", "example": "約束は守るべきです。", "exampleZh": "應該遵守約定。", "note": "道德或義務上的應該。"},
    {"title": "かもしれない — 也許", "pattern": "普通形 + かもしれない", "example": "明日は雨かもしれません。", "exampleZh": "明天也許會下雨。", "note": "不確定的推測。"},
    {"title": "に違いない — 一定", "pattern": "普通形 + に違いない", "example": "彼は知っているに違いない。", "exampleZh": "他一定知道。", "note": "強烈肯定推測。"},
    {"title": "てあげる / てくれる / てもらう", "pattern": "て形 + あげる/くれる/もらう", "example": "友達が教えてくれました。", "exampleZh": "朋友教了我。", "note": "給予/為我/得到恩惠。"},
    {"title": "意向形 — 意志", "pattern": "動詞意向形", "example": "一緒に行きましょう。", "exampleZh": "一起去吧。", "note": "表達意志，ましょう 為禮貌形式。"},
    {"title": "可能形 — 能夠", "pattern": "動詞可能形", "example": "日本語が話せます。", "exampleZh": "會說日語。", "note": "五段動詞可能形與一段動詞 られる。"},
    {"title": "受身形 — 被動", "pattern": "動詞受身形", "example": "先生に褒められました。", "exampleZh": "被老師稱讚了。", "note": "被動或尊稱受益。"},
    {"title": "使役形 — 使令", "pattern": "動詞使役形", "example": "子供に野菜を食べさせます。", "exampleZh": "讓孩子吃蔬菜。", "note": "使/讓某人做。"},
    {"title": "敬語 — 尊敬・謙讓", "pattern": "お/ご + ます / いらっしゃる", "example": "先生がいらっしゃいます。", "exampleZh": "老師在。", "note": "N4 基礎敬語入門。"},
    {"title": "と思う — 認為", "pattern": "普通形 + と思う", "example": "明日は晴れると思います。", "exampleZh": "我認為明天會放晴。", "note": "表達個人想法。"},
    {"title": "と言う — 叫做・說", "pattern": "普通形 + と言う", "example": "田中さんと言います。", "exampleZh": "叫做田中。", "note": "引用或命名。"},
    {"title": "場合は — 場合", "pattern": "普通形 + 場合は", "example": "雨の場合は、中止です。", "exampleZh": "下雨的話就取消。", "note": "假設情況。"},
    {"title": "最中に — 正當…時", "pattern": "最中に", "example": "食事の最中に電話が鳴りました。", "exampleZh": "吃飯時電話響了。", "note": "正在進行某事時。"},
    {"title": "によって — 根據・由於", "pattern": "名詞 + によって", "example": "人によって違います。", "exampleZh": "因人而異。", "note": "依據、原因、手段。"},
]

CATEGORY_RULES = [
    ("greetings", "👋 打招呼・禮貌", lambda e, r, m, t: any(k in m.lower() for k in ["hello", "goodbye", "thank", "sorry", "please", "excuse", "welcome", "congratulation"]) or e in ("おはよう", "こんにちは", "こんばんは", "ありがとう", "すみません", "さようなら", "はじめまして", "いただきます", "ごちそうさま")),
    ("numbers_time", "🔢 數字・時間", lambda e, r, m, t: any(k in m.lower() for k in ["number", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "hundred", "thousand", "minute", "hour", "day", "week", "month", "year", "morning", "afternoon", "evening", "night", "today", "tomorrow", "yesterday", "time", "o'clock", "what time"]) or re.match(r"^[一二三四五六七八九十百千万]+", e) or e.endswith("時") or e.endswith("分") or e.endswith("月") or e.endswith("日")),
    ("family_people", "👨‍👩‍👧 人物・家族", lambda e, r, m, t: any(k in m.lower() for k in ["person", "people", "man", "woman", "child", "baby", "father", "mother", "parent", "brother", "sister", "family", "friend", "student", "teacher", "doctor", "mr.", "mrs.", "miss", "grandfather", "grandmother", "husband", "wife", "boy", "girl"])),
    ("body_health", "🫀 身體・健康", lambda e, r, m, t: any(k in m.lower() for k in ["body", "head", "face", "eye", "ear", "nose", "mouth", "hand", "foot", "leg", "arm", "finger", "tooth", "hair", "sick", "ill", "pain", "medicine", "hospital", "health", "fever", "cold"])),
    ("food_drink", "🍱 飲食", lambda e, r, m, t: any(k in m.lower() for k in ["food", "eat", "drink", "rice", "bread", "meat", "fish", "vegetable", "fruit", "tea", "coffee", "water", "milk", "sugar", "salt", "cook", "meal", "breakfast", "lunch", "dinner", "restaurant", "delicious", "hungry", "thirsty", "beer", "wine", "juice", "egg", "noodle", "soup"])),
    ("places", "📍 場所・建築", lambda e, r, m, t: any(k in m.lower() for k in ["place", "building", "house", "home", "room", "school", "hospital", "station", "airport", "hotel", "shop", "store", "bank", "post office", "library", "park", "toilet", "bathroom", "kitchen", "door", "window", "floor", "city", "country", "town", "company", "office", "museum", "temple", "shrine"])),
    ("transport", "🚃 交通", lambda e, r, m, t: any(k in m.lower() for k in ["train", "bus", "car", "taxi", "bicycle", "walk", "drive", "fly", "airplane", "ship", "ticket", "traffic", "road", "street", "bridge", "travel", "trip"])),
    ("nature_weather", "🌤️ 自然・天氣", lambda e, r, m, t: any(k in m.lower() for k in ["weather", "rain", "snow", "wind", "cloud", "sun", "moon", "star", "sky", "sea", "river", "mountain", "tree", "flower", "animal", "dog", "cat", "bird", "fish", "hot", "cold", "warm", "cool", "season", "spring", "summer", "autumn", "winter"])),
    ("clothing", "👕 衣物", lambda e, r, m, t: any(k in m.lower() for k in ["clothes", "shirt", "pants", "shoes", "hat", "wear", "sock", "coat", "dress", "skirt", "uniform", "glasses", "watch", "bag"])),
    ("colors_shapes", "🎨 顏色・形狀", lambda e, r, m, t: any(k in m.lower() for k in ["color", "colour", "red", "blue", "green", "yellow", "black", "white", "brown", "pink", "purple", "orange", "gray", "grey", "shape", "round", "square", "long", "short", "wide", "narrow"])),
    ("school_study", "📚 學校・學習", lambda e, r, m, t: any(k in m.lower() for k in ["study", "learn", "school", "class", "homework", "test", "exam", "book", "pen", "pencil", "paper", "dictionary", "language", "question", "answer", "university", "college"])),
    ("work_business", "💼 工作・商務", lambda e, r, m, t: any(k in m.lower() for k in ["work", "job", "business", "company", "meeting", "salary", "money", "pay", "sell", "buy", "price", "cheap", "expensive", "customer", "product"])),
    ("verbs", "🏃 動詞", lambda e, r, m, t: m.lower().startswith("to ") and not any(k in m.lower() for k in ["to be", "to become"])),
    ("i_adjectives", "🔴 い形容詞", lambda e, r, m, t: (e.endswith("い") and len(e) > 1 and not e.endswith("ます")) or "い-adjective" in m.lower() or ("adjective" in m.lower() and "い" in m)),
    ("na_adjectives", "🔵 な形容詞", lambda e, r, m, t: "na-adjective" in m.lower() or ("adjective" in m.lower() and "na" in m.lower())),
    ("adverbs", "⚡ 副詞", lambda e, r, m, t: any(k in m.lower() for k in ["very", "always", "often", "sometimes", "never", "quickly", "slowly", "already", "still", "yet", "almost", "quite", "adverb"]) or e.endswith("に") and len(e) <= 4),
    ("katakana", "🔤 外來語", lambda e, r, m, t: is_katakana(e)),
    ("expressions", "💬 慣用表現", lambda e, r, m, t: "expression" in t.lower() or len(e) > 6 and "、" in m),
]

def is_katakana(s):
    for c in s:
        if c in 'ー・':
            continue
        if '\u30a0' <= c <= '\u30ff':
            continue
        if c.isascii() and c.isalpha():
            continue
        if '\u4e00' <= c <= '\u9fff' or '\u3040' <= c <= '\u309f':
            return False
    return any('\u30a0' <= c <= '\u30ff' for c in s)

def categorize(expression, reading, meaning, tags):
    for key, label, rule in CATEGORY_RULES:
        try:
            if rule(expression, reading, meaning, tags):
                return key, label
        except Exception:
            pass
    if meaning.lower().startswith("to "):
        return "verbs", "🏃 動詞"
    if "adjective" in meaning.lower():
        return "i_adjectives", "🔴 い形容詞"
    return "nouns", "📦 名詞"

def load_cache():
    if CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    return {}

def save_cache(cache):
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")

def translate_meaning(en_text, cache, translator=None):
    if en_text in cache:
        return cache[en_text]
    if not HAS_TRANSLATOR or translator is None:
        short = re.split(r'[,;]', en_text)[0].strip()
        cache[en_text] = short
        return short
    short = re.split(r'[,;]', en_text)[0].strip()
    try:
        zh = translator.translate(short)
        cache[en_text] = zh
        time.sleep(0.08)
        return zh
    except Exception:
        cache[en_text] = short
        return short

def pretranslate_all(rows, cache):
    """Translate unique meanings once."""
    unique = []
    for row in rows:
        m = row["meaning"].strip().strip('"')
        if m not in cache:
            unique.append(m)
    unique = list(dict.fromkeys(unique))
    if not HAS_TRANSLATOR or not unique:
        return cache
    translator = GoogleTranslator(source="en", target="zh-TW")
    print(f"  Translating {len(unique)} new meanings...")
    for i, m in enumerate(unique):
        translate_meaning(m, cache, translator)
        if (i + 1) % 100 == 0:
            print(f"  ... {i+1}/{len(unique)}", flush=True)
            save_cache(cache)
    save_cache(cache)
    return cache

def read_csv(level):
    path = BASE / f"{level}.csv"
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows

def build_vocab(level, cache):
    rows = read_csv(level)
    cache = pretranslate_all(rows, cache)
    categories = {}
    seen = set()

    for row in rows:
        expr = row["expression"].strip()
        reading = row["reading"].strip()
        meaning = row["meaning"].strip().strip('"')
        tags = row.get("tags", "")

        key = (expr, reading)
        if key in seen:
            continue
        seen.add(key)

        cat_key, cat_label = categorize(expr, reading, meaning, tags)
        if cat_key not in categories:
            categories[cat_key] = {"label": cat_label, "words": []}

        zh = translate_meaning(meaning, cache)

        categories[cat_key]["words"].append({
            "jp": expr if expr else reading,
            "romaji": reading,
            "zh": zh,
        })
    # Sort categories by label, words alphabetically by jp
    ordered = dict(sorted(categories.items(), key=lambda x: x[1]["label"]))
    for cat in ordered.values():
        cat["words"].sort(key=lambda w: w["jp"])
    return ordered

def to_js(name, obj):
  lines = [f"const {name} = "]
  lines.append(json.dumps(obj, ensure_ascii=False, indent=2))
  lines.append(";")
  return "\n".join(lines)

def main():
    cache = load_cache()
    print("Building N5 vocabulary...")
    n5_vocab = build_vocab("n5", cache)
    n5_count = sum(len(c["words"]) for c in n5_vocab.values())
    print(f"N5: {n5_count} words in {len(n5_vocab)} categories")

    print("Building N4 vocabulary...")
    n4_vocab = build_vocab("n4", cache)
    n4_count = sum(len(c["words"]) for c in n4_vocab.values())
    print(f"N4: {n4_count} words in {len(n4_vocab)} categories")

    n5_data = {
        "label": "N5",
        "badgeClass": "bg-emerald-100 text-emerald-700",
        "desc": f"入門級｜{n5_count} 單字｜{len(N5_GRAMMAR)} 文法｜五十音・基礎日常會話",
        "hasKana": True,
        "vocab": n5_vocab,
        "grammar": N5_GRAMMAR,
    }
    n4_data = {
        "label": "N4",
        "badgeClass": "bg-blue-100 text-blue-700",
        "desc": f"初級｜{n4_count} 單字｜{len(N4_GRAMMAR)} 文法｜進階句型・動詞活用",
        "hasKana": False,
        "vocab": n4_vocab,
        "grammar": N4_GRAMMAR,
    }

    (BASE / "nihongo-n5.js").write_text(to_js("N5_DATA", n5_data), encoding="utf-8")
    (BASE / "nihongo-n4.js").write_text(to_js("N4_DATA", n4_data), encoding="utf-8")
    print("Done: nihongo-n5.js, nihongo-n4.js")

if __name__ == "__main__":
    main()
