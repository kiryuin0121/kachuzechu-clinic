DROP DATABASE IF EXISTS OH_PY23DB_IH12A_38;
CREATE DATABASE OH_PY23DB_IH12A_38 CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE OH_PY23DB_IH12A_38;

-- ユーザーテーブル
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    email VARCHAR(255) UNIQUE NOT NULL, 
    hashed_password VARCHAR(255) NOT NULL,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- メール検証トークン管理テーブル
CREATE TABLE verifications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    token VARCHAR(255) UNIQUE NOT NULL,
    new_email VARCHAR(255) NULL,
    type VARCHAR(50) NOT NULL DEFAULT 'registration',
    expires_at DATETIME NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 早口言葉テーブル
CREATE TABLE tongue_twisters (
    id INT PRIMARY KEY AUTO_INCREMENT,
    phrase TEXT NOT NULL,
    furigana TEXT NOT NULL,
    difficulty INT NOT NULL,
    -- 早口言葉を発話する目標時間
    target_duration FLOAT NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 練習記録テーブル
CREATE TABLE logs (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NULL,
    tongue_twister_id INT NOT NULL,
    phrase_log TEXT,
    hiragana_log TEXT,
    duration_log FLOAT NOT NULL,
    accuracy_score FLOAT NOT NULL,
    speed_score FLOAT NOT NULL,
    total_score FLOAT NOT NULL,
    audio_path VARCHAR(255) NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (tongue_twister_id) REFERENCES tongue_twisters(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_verifications_token ON verifications(token);
CREATE INDEX idx_verifications_user_id ON verifications(user_id);
CREATE INDEX idx_logs_user_id ON logs(user_id);
CREATE INDEX idx_logs_tongue_twister_id ON logs(tongue_twister_id);
CREATE INDEX idx_logs_created_at ON logs(created_at);
CREATE INDEX idx_logs_user_tongue_created_at ON logs(user_id, tongue_twister_id, created_at);

/*
  早口言葉マスターデータの投入処理
  https://frenchbread-sorrow.com/hayakuchi/
*/

INSERT INTO tongue_twisters (phrase, furigana, difficulty, target_duration) VALUES
('生麦生米生卵','なまむぎなまごめなまたまご',1,5.1),
('バスガス爆発','ばすがすばくはつ',1,3.3),
('隣の客はよく柿食う客だ','となりのきゃくはよくかきくうきゃくだ',1,6.1),
('貨客船万景峰号','かきゃくせんまんぎょんぼんごう',1,5.1),
('老若男女','ろうにゃくなんにょ',1,3.0),
('骨粗鬆症','こつそしょうしょう',1,3.0),
('生バナナ','なまばなな',1,2.3),
('魔術師魔術修行中','まじゅつしまじゅつしゅぎょうちゅう',1,4.7),
('神アニメ','かみあにめ',1,2.3),
('赤パジャマ黄パジャマ青パジャマ','あかぱじゃまきぱじゃまあおぱじゃま',1,5.4),
('裏庭には二羽鶏がいる','うらにわにはにわにわとりがいる',1,5.8),
('駒大苫小牧','こまだいとまこまい',1,3.7),
('4tの養豚場','よんとんのようとんじょう',1,4.4),
('アイスアイスアイスアイスアイス','あいすあいすあいすあいすあいす',1,5.8),
('赤巻紙青巻紙黄巻紙','あかまきがみあおまきがみきまきがみ',2,6.9),
('スモモも桃も桃のうち','すもももももももものうち',2,5.0),
('炙りカルビ','あぶりかるび',2,2.8),
('旅客機の旅客','りょきゃくきのりょきゃく',2,3.5),
('ヨーロッパ旅行客','よーろっぱりょこうきゃく',2,4.3),
('バナナババロア','ばななばばろあ',2,3.1),
('新設診察室視察','しんせつしんさつしつしさつ',2,5.4),
('砂漠で油売るアラブの油売り','さばくであぶらうるあらぶのあぶらうり',2,7.3),
('坊主が屏風に上手に坊主の絵を描いた','ぼうずがびょうぶにじょうずにぼうずのえをかいた',2,8.4),
('夏の生夏豆','なつのなまなつまめ',2,3.9),
('パン壁','ぱんかべ',2,2.0),
('壁パク','かべぱく',2,2.0),
('巨漢キャラ','きょかんきゃら',2,2.4),
('公序良俗','こうじょりょうぞく',2,3.1),
('腹腔鏡手術','ふくくうきょうしゅじゅつ',2,3.9),
('白装束集団','しろしょうぞくしゅうだん',2,4.3),
('赤坂サカスでサーカス探す','あかさかさかすでさーかすさがす',2,6.1),
('ブラジル人のミラクルビラ配り','ぶらじるじんのみらくるびらくばり',2,6.5),
('肩叩き機','かたたたきき',3,2.9),
('赤パジャマ黄パジャマ茶パジャマ','あかぱじゃまきぱじゃまちゃぱじゃま',3,5.7),
('摘出手術','てきしゅつしゅじゅつ',3,3.3),
('奈良ならのろのろ運転で行け','ならならのろのろうんてんでいけ',3,6.5),
('可逆反応の逆不可逆反応','かぎゃくはんのうのぎゃくふかぎゃくはんのう',3,7.7),
('新進シャンソン歌手新春シャンソンショー','しんしんしゃんそんかしゅしんしゅんしゃんそんしょー',3,8.5),
('子亀孫亀曾孫亀','こがめまごがめひまごがめ',3,5.3),
('高速増殖炉もんじゅ','こうそくぞうしょくろもんじゅ',3,5.3),
('バナナなどを戸棚などの中に入れる','ばなななどをとだななどのなかにいれる',3,7.7),
('赤炙りカルビ青炙りカルビ黄炙りカルビ','あかあぶりかるびあおあぶりかるびきあぶりかるび',3,9.7),
('魔術師が美術室で手術中','まじゅつしがびじゅつしつでしゅじゅつちゅう',3,6.9),
('消費者少子化担当大臣','しょうひしゃしょうしかたんとうだいじん',3,6.9),
('マサチューセッツ州で手術中','まさちゅーせっつしゅうでしゅじゅつちゅう',3,6.5),
('パッペパッペパペピョパペピョン','ぱっぺぱっぺぱぺぴょぱぺぴょん',3,5.7),
('東京特許許可局局長','とうきょうとっきょきょかきょくきょくちょう',4,6.9),
('404泊405日','よんひゃくよんはくよんひゃくいつか',4,6.9),
('低所得者層','ていしょとくしゃそう',4,3.9),
('除雪車除雪作業中','じょせつしゃじょせつさぎょうちゅう',4,5.6),
('赤アロエ飴青アロエ飴黄アロエ飴','あかあろえあめあおあろえあめきあろえあめ',4,9.1),
('お綾や親にお謝り','おあややおやにおあやまり',4,5.6),
('竹藪に竹立て掛けたのは竹立て掛けたかったから立て掛けた','たけやぶにたけたてかけたのはたけたてかけたかったからたてかけた',4,13.8),
('シャア少佐除雪車操縦中','しゃあしょうさじょせつしゃそうじゅうちゅう',4,6.9),
('平山あやヒマラヤで平謝り','ひらやまあやひまらやでひらあやまり',4,7.8),
('地図帳でチェジュ島を探す','ちずちょうでちぇじゅとうをさがす',4,6.1),
('輸出車輸出湯輸出酢','ゆしゅつしゃゆしゅつゆゆしゅつす',4,5.6),
('右目右耳右耳右目','みぎめみぎみみみぎみみみぎめ',4,6.5),
('抜きにくい釘引きにくい釘引き抜きにくい釘','ぬきにくいくぎひきにくいくぎひきぬきにくいくぎ',4,10.4),
('家のつるべは潰れぬつるべ隣のつるべは潰れるつるべ','いえのつるべはつぶれぬつるべとなりのつるべはつぶれるつるべ',4,12.9),
('ミニ右耳右に2ミリ','みにみぎみみみぎににみり',4,5.6),
('生産者の申請書審査','せいさんしゃのしんせいしょしんさ',4,6.5),
('勝った方戦った鷹','かったかたたたかったたか',4,5.6),
('商社の社長が調査書捜査','しょうしゃのしゃちょうがちょうさしょそうさ',5,7.4),
('きゃりーぱみゅぱみゅ','きゃりーぱみゅぱみゅ',5,3.7),
('集中治療室で集中手術中','しゅうちゅうちりょうしつでしゅうちゅうしゅじゅつちゅう',5,9.3),
('東京特許許可局局長急遽許可却下','とうきょうとっきょきょかきょくきょくちょうきゅうきょきょかきゃっか',5,11.1),
('日本国庫局東京特許許可局','にほんこっこきょくとうきょうとっきょきょかきょく',5,9.3),
('骨粗鬆症訴訟勝訴','こつそしょうしょうそしょうしょうそ',5,6.5),
('シチュー死守しつつ試食し視聴中','しちゅーししゅしつつししょくししちょうちゅう',5,8.3),
('新出シャンソン歌手総出演新春シャンソンショー','しんしゅつしゃんそんかしゅそうしゅつえんしんしゅんしゃんそんしょー',5,12.5),
('消費支出費非消費支出費','しょうひししゅつひひしょうひししゅつひ',5,7.4),
('社長支社長司書室長','しゃちょうししゃちょうししょしつちょう',5,6.5);

SELECT COUNT(*) AS total_count FROM tongue_twisters;
SELECT difficulty, COUNT(*) AS count FROM tongue_twisters GROUP BY difficulty ORDER BY difficulty;

SELECT 'データベース初期化が完了しました。' AS message;
