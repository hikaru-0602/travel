import streamlit as st
import openai
import os
from dotenv import load_dotenv
import requests
import json
import re
from datetime import datetime, timedelta

# .envファイルを読み込む
load_dotenv()

# OpenAI APIキーを設定
openai.api_key = os.getenv("OPENAI_API_KEY")

# 楽天API設定
RAKUTEN_APP_ID = os.getenv("RAKUTEN_APP_ID")

# Google Geocoding API設定
GOOGLE_GEOCODING_API_KEY = os.getenv("GOOGLE_GEOCODING_API_KEY")

def get_coordinates_from_google_geocoding(location_text):
    """Google Geocoding APIを使って地名から緯度経度を取得（WGS84・度単位）"""
    if not GOOGLE_GEOCODING_API_KEY:
        return {}

    try:
        # Google Geocoding API URL
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {
            'address': location_text + ', Japan',  # 日本国内検索を明示
            'key': GOOGLE_GEOCODING_API_KEY,
            'language': 'ja',  # 日本語レスポンス
            'region': 'jp'     # 日本地域を優先
        }

        response = requests.get(url, params=params)
        response.raise_for_status()

        data = response.json()

        if data['status'] == 'OK' and data['results']:
            result = data['results'][0]  # 最初の結果を使用
            location = result['geometry']['location']

            # WGS84度単位を日本測地系秒単位に変換
            # WGS84 -> 日本測地系の変換（近似値）
            lat_wgs84 = location['lat']
            lng_wgs84 = location['lng']

            # 日本測地系への変換（簡易変換、正確にはより複雑な計算が必要）
            # 一般的な変換パラメータ
            lat_jgd = lat_wgs84 - 0.00010695 * lat_wgs84 + 0.000017464 * lng_wgs84 + 0.0046017
            lng_jgd = lng_wgs84 - 0.000046038 * lat_wgs84 - 0.000083043 * lng_wgs84 + 0.010040

            # 度を秒に変換（1度 = 3600秒）
            lat_seconds = lat_jgd * 3600
            lng_seconds = lng_jgd * 3600

            return {
                'latitude': round(lat_seconds, 2),
                'longitude': round(lng_seconds, 2),
                'location_name': result['formatted_address'],
                'source': 'google_geocoding',
                'wgs84_lat': lat_wgs84,
                'wgs84_lng': lng_wgs84
            }
        else:
            return {}

    except Exception as e:
        st.error(f"Google Geocoding API エラー: {str(e)}")
        return {}

def get_coordinates_from_location(location_text):
    """地名から緯度経度を取得（Google Geocoding API優先、フォールバックでOpenAI）"""

    # 最初にGoogle Geocoding APIを試す
    if GOOGLE_GEOCODING_API_KEY:
        coordinates = get_coordinates_from_google_geocoding(location_text)
        if coordinates:
            return coordinates

    # Google APIが利用できない場合はOpenAIを使用
    return get_coordinates_from_openai(location_text)

def get_coordinates_from_openai(location_text):
    """OpenAIを使って地名から緯度経度を取得（日本測地系・秒単位）- フォールバック用"""
    if not openai.api_key:
        return {}

    system_prompt = """
あなたは地名から緯度経度を取得するアシスタントです。

ユーザーが入力した地名に基づいて、その場所の緯度（latitude）と経度（longitude）を返してください。

重要な注意事項：
- 日本測地系（Tokyo Datum）での値を返してください
- 単位は秒で返してください（度ではありません）
- ミリ秒は小数点以下2桁以内で返してください
- 緯度は北緯（正の値）、経度は東経（正の値）で返してください

必ずJSON形式で返答してください：
{"latitude": 緯度の秒数値, "longitude": 経度の秒数値, "location_name": "正式な地名"}

例（日本測地系・秒単位）：
- 東京駅: {"latitude": 128440.51, "longitude": 503172.21, "location_name": "東京駅"}
- 銀座: {"latitude": 128400.84, "longitude": 503154.89, "location_name": "東京都中央区銀座"}

注意：1度 = 3600秒です。日本測地系で正確に計算してください。
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"次の地名の緯度経度を日本測地系・秒単位で教えてください: {location_text}"}
            ],
            temperature=0.1,
            max_tokens=200
        )

        result_text = response.choices[0].message.content

        # JSONレスポンスを解析
        try:
            json_match = re.search(r'\{.*\}', result_text, re.DOTALL)
            if json_match:
                coordinates = json.loads(json_match.group())
                # 緯度経度をミリ秒小数点以下2桁まで丸める
                if 'latitude' in coordinates:
                    coordinates['latitude'] = round(float(coordinates['latitude']), 2)
                if 'longitude' in coordinates:
                    coordinates['longitude'] = round(float(coordinates['longitude']), 2)
                coordinates['source'] = 'openai'
                return coordinates
        except:
            pass

        return {}

    except Exception as e:
        st.error(f"緯度経度取得エラー: {str(e)}")
        return {}

def format_date_no_padding(date_obj):
    """日付をゼロパディングなしの形式でフォーマット（クロスプラットフォーム対応）"""
    return f"{date_obj.year}-{date_obj.month}-{date_obj.day}"

def parse_travel_request_with_openai(text):
    """OpenAI APIを使用して自然言語の入力を楽天トラベルAPIのパラメータに変換"""
    if not openai.api_key:
        return {"error": "OpenAI APIキーが設定されていません"}

    # 楽天トラベルAPI用のFunction定義
    functions = [
        {
            "name": "search_rakuten_hotels",
            "description": "楽天トラベル空室検索APIのパラメータを抽出する",
            "parameters": {
                "type": "object",
                "properties": {
                    "checkinDate": {
                        "type": "string",
                        "description": "チェックイン日 (YYYY-M-D形式、ゼロパディングなし)",
                        "pattern": "^\\d{4}-\\d{1,2}-\\d{1,2}$"
                    },
                    "checkoutDate": {
                        "type": "string",
                        "description": "チェックアウト日 (YYYY-M-D形式、ゼロパディングなし)",
                        "pattern": "^\\d{4}-\\d{1,2}-\\d{1,2}$"
                    },
                    "adultNum": {
                        "type": "integer",
                        "description": "大人の人数",
                        "minimum": 1,
                        "maximum": 99
                    },
                    "childNum": {
                        "type": "integer",
                        "description": "子供の人数",
                        "minimum": 0,
                        "maximum": 99
                    },
                    "location": {
                        "type": "string",
                        "description": "宿泊場所・地名（都道府県、市区町村、観光地名など）"
                    },
                    "maxCharge": {
                        "type": "integer",
                        "description": "最大料金（円）",
                        "minimum": 0
                    },
                    "minCharge": {
                        "type": "integer",
                        "description": "最小料金（円）",
                        "minimum": 0
                    },
                    "searchRadius": {
                        "type": "integer",
                        "description": "検索半径（km）",
                        "minimum": 1,
                        "maximum": 3,
                        "default": 1
                    }
                },
                "required": []
            }
        }
    ]

    # システムプロンプト
    system_prompt = f"""
あなたは楽天トラベル検索アシスタントです。ユーザーの自然言語での宿泊検索要求を、楽天トラベル空室検索APIのパラメータに変換してください。

## 重要な変換ルール：

### 日付処理：
- 今日の日付: {format_date_no_padding(datetime.now())}
- 「今日」「明日」「明後日」などの相対日付を具体的な日付に変換
- 「12月1日」「12/1」などを今年の日付として解釈
- 泊数が指定された場合、チェックアウト日を自動計算
- 日付形式はYYYY-M-D（ゼロパディングなし、例：2024-6-1）

### 地域指定：
- 地名は「location」フィールドに抽出してください
- 都道府県名、市区町村名、観光地名、駅名なども含めて抽出
- 略語や俗称も正式名称として認識
- 地名から日本測地系の緯度経度（秒単位）を取得して位置ベース検索を行います

### 検索範囲：
- searchRadius: 検索半径（1-3km、デフォルト1km）

### デフォルト値：
- 人数が指定されていない場合: adultNum = 2
- 泊数が指定されていない場合: 1泊として処理
- 検索半径が指定されていない場合: searchRadius = 1

ユーザーの入力から必要なパラメータを抽出し、search_rakuten_hotels関数を呼び出してください。
"""

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"以下の検索条件をAPIパラメータに変換してください: {text}"}
            ],
            functions=functions,
            function_call={"name": "search_rakuten_hotels"},
            temperature=0.1
        )

        # Function callの結果を取得
        function_call = response.choices[0].message.function_call
        if function_call and function_call.name == "search_rakuten_hotels":
            params = json.loads(function_call.arguments)

            # 地名が指定されている場合、緯度経度を取得
            if 'location' in params and params['location']:
                coordinates = get_coordinates_from_location(params['location'])
                if coordinates and 'latitude' in coordinates and 'longitude' in coordinates:
                    # 緯度経度をパラメータに追加（日本測地系・秒単位、小数点以下2桁まで）
                    params['latitude'] = round(float(coordinates['latitude']), 2)
                    params['longitude'] = round(float(coordinates['longitude']), 2)

                    # searchRadiusがない場合はデフォルト値を設定
                    if 'searchRadius' not in params:
                        params['searchRadius'] = 2

                    params['coordinate_match'] = {
                        'original_location': params['location'],
                        'coordinates': coordinates
                    }

                    # 緯度経度ベース検索のためlocationフィールドは削除
                    del params['location']
                else:
                    params['coordinate_failed'] = True

            return params
        else:
            return {"error": "パラメータの抽出に失敗しました"}

    except Exception as e:
        return {"error": f"OpenAI API エラー: {str(e)}"}

def search_rakuten_hotels(params):
    """楽天トラベル空室検索APIを呼び出す（緯度経度ベース）"""
    if not RAKUTEN_APP_ID:
        return {"error": "楽天APIキーが設定されていません"}

    base_url = "https://app.rakuten.co.jp/services/api/Travel/VacantHotelSearch/20170426"

    # 必須パラメータの追加
    api_params = {
        'applicationId': RAKUTEN_APP_ID,
        'format': 'json',
        'formatVersion': 1
    }

    # 検索パラメータの追加（内部情報は除外）
    for key, value in params.items():
        if key not in ['coordinate_match', 'coordinate_failed']:
            api_params[key] = value

    # デバッグモードの場合、APIパラメータを表示
    if st.session_state.get('debug_mode', False):
        st.write("**楽天API呼び出しパラメータ:**")
        st.json(api_params)
        st.write(f"**API URL:** {base_url}")

    try:
        response = requests.get(base_url, params=api_params)

        # デバッグモードの場合、HTTPレスポンス情報を表示
        if st.session_state.get('debug_mode', False):
            st.write(f"**HTTPステータスコード:** {response.status_code}")
            st.write(f"**レスポンスヘッダー:** {dict(response.headers)}")

        response.raise_for_status()
        result = response.json()

        # デバッグモードの場合、生のレスポンスを表示
        if st.session_state.get('debug_mode', False):
            st.write("**楽天API生レスポンス:**")
            st.json(result)

        return result

    except requests.exceptions.RequestException as e:
        error_msg = f"API呼び出しエラー: {str(e)}"

        # デバッグモードの場合、詳細なエラー情報を表示
        if st.session_state.get('debug_mode', False):
            if hasattr(e, 'response') and e.response is not None:
                st.write(f"**エラーレスポンス内容:** {e.response.text}")

        return {"error": error_msg}

def format_hotel_results(results):
    """ホテル検索結果をより見やすい形式で表示"""
    if "error" in results:
        st.error(f"❌ エラー: {results['error']}")
        return

    # APIレスポンスの構造をデバッグ表示
    if st.session_state.get('debug_mode', False):
        st.write("**APIレスポンス構造（デバッグ）:**")
        st.json(results)

    if 'hotels' not in results or not results['hotels']:
        st.info("🔍 該当するホテルが見つかりませんでした。")
        return

    # ページング情報の表示
    if 'pagingInfo' in results:
        paging = results['pagingInfo']
        record_count = paging.get('recordCount', 0)
        st.success(f"📊 **検索結果**: {record_count}件のホテルが見つかりました")

    # 結果をリスト形式で表示
    st.subheader("🏨 ホテル一覧")

    try:
        hotels_data = results['hotels']

        # デバッグ情報表示
        if st.session_state.get('debug_mode', False):
            st.write(f"**hotels データの型**: {type(hotels_data)}")
            st.write(f"**hotels データの長さ**: {len(hotels_data) if hasattr(hotels_data, '__len__') else 'N/A'}")

            if hotels_data:
                if isinstance(hotels_data, dict):
                    keys = list(hotels_data.keys())[:5]  # 最初の5個のキー
                    st.write(f"**hotels の最初の5個のキー**: {keys}")
                elif isinstance(hotels_data, list):
                    st.write(f"**最初のホテルデータの型**: {type(hotels_data[0]) if len(hotels_data) > 0 else 'N/A'}")
                    if len(hotels_data) > 0 and isinstance(hotels_data[0], dict):
                        st.write(f"**最初のホテルデータのキー**: {list(hotels_data[0].keys())}")
                        if 'hotel' in hotels_data[0]:
                            st.write(f"**hotel配列の型**: {type(hotels_data[0]['hotel'])}")
                            st.write(f"**hotel配列の長さ**: {len(hotels_data[0]['hotel']) if hasattr(hotels_data[0]['hotel'], '__len__') else 'N/A'}")

        hotel_count = 0
        max_hotels = 100  # 最大表示数

        def extract_hotel_info(hotel_data_item):
            """ホテル情報を抽出する汎用関数"""
            hotel_basic_info = None
            room_info = None

            # パターン1: hotelBasicInfo と roomInfo が直接存在
            if isinstance(hotel_data_item, dict):
                if 'hotelBasicInfo' in hotel_data_item:
                    hotel_basic_info = hotel_data_item['hotelBasicInfo']
                if 'roomInfo' in hotel_data_item:
                    room_info = hotel_data_item['roomInfo']

                # パターン2: hotel キーの下にhotelBasicInfo等が存在
                if 'hotel' in hotel_data_item:
                    hotel_array = hotel_data_item['hotel']
                    if isinstance(hotel_array, list):
                        for item in hotel_array:
                            if isinstance(item, dict):
                                if 'hotelBasicInfo' in item:
                                    hotel_basic_info = item['hotelBasicInfo']
                                if 'roomInfo' in item:
                                    room_info = item['roomInfo']
                    elif isinstance(hotel_array, dict):
                        if 'hotelBasicInfo' in hotel_array:
                            hotel_basic_info = hotel_array['hotelBasicInfo']
                        if 'roomInfo' in hotel_array:
                            room_info = hotel_array['roomInfo']

                # パターン3: 直接ホテル情報が格納されている場合
                if not hotel_basic_info and 'hotelName' in hotel_data_item:
                    hotel_basic_info = hotel_data_item

            return hotel_basic_info, room_info

        def format_single_hotel(hotel_basic_info, room_info, index):
            """単一ホテルの情報を見やすいカード形式でフォーマット"""
            if not hotel_basic_info:
                return

            # 基本情報の取得
            name = hotel_basic_info.get('hotelName', '名前不明')
            min_charge = hotel_basic_info.get('hotelMinCharge', 'N/A')
            access = hotel_basic_info.get('access', '交通情報なし')
            address1 = hotel_basic_info.get('address1', '')
            address2 = hotel_basic_info.get('address2', '')
            address = f"{address1}{address2}".strip()
            review_average = hotel_basic_info.get('reviewAverage', 'N/A')
            review_count = hotel_basic_info.get('reviewCount', 0)
            hotel_image_url = hotel_basic_info.get('hotelImageUrl', '')
            hotel_info_url = hotel_basic_info.get('hotelInformationUrl', '')
            plan_list_url = hotel_basic_info.get('planListUrl', '')
            hotel_special = hotel_basic_info.get('hotelSpecial', '')

            # review_countがNoneの場合は0に変換
            if review_count is None:
                review_count = 0

            # Streamlitのcontainerを使って見やすく表示
            with st.container():
                # ホテル名をヘッダーに
                st.markdown(f"### {index}. {name}")

                # カラムで情報を整理
                col1, col2 = st.columns([2, 1])

                with col1:
                    # 基本情報
                    if min_charge != 'N/A':
                        st.markdown(f"💰 **最低料金**: ¥{min_charge:,}〜")

                    if address:
                        st.markdown(f"📍 **住所**: {address}")

                    st.markdown(f"🚃 **アクセス**: {access}")

                    # 評価情報
                    if review_average != 'N/A' and review_count > 0:
                        # 星の表示
                        stars = "⭐" * min(int(float(review_average)), 5)
                        st.markdown(f"{stars} **{review_average}** ({review_count}件のレビュー)")

                    # 特典情報
                    if hotel_special:
                        with st.expander("🎯 特典・サービス"):
                            st.write(hotel_special)

                with col2:
                    # ホテル画像
                    if hotel_image_url:
                        try:
                            st.image(hotel_image_url, caption="ホテル画像", use_container_width=True)
                        except:
                            st.write("🖼️ 画像を読み込めませんでした")

                # 料金情報（roomInfoから取得）
                if room_info and isinstance(room_info, list):
                    for room in room_info:
                        if isinstance(room, dict):
                            if 'dailyCharge' in room:
                                daily_charge = room['dailyCharge']
                                if isinstance(daily_charge, dict) and 'total' in daily_charge:
                                    st.markdown(f"💳 **宿泊料金**: ¥{daily_charge['total']:,}（総額）")
                                    break

                # リンクボタン
                link_cols = st.columns(3)

                with link_cols[0]:
                    if hotel_info_url:
                        st.link_button("📋 詳細情報", hotel_info_url)

                with link_cols[1]:
                    if plan_list_url:
                        st.link_button("🏨 プラン一覧", plan_list_url)

                with link_cols[2]:
                    if hotel_image_url:
                        st.link_button("🖼️ 画像", hotel_image_url)

                # 区切り線
                st.divider()

        # 様々なデータ構造に対応
        if isinstance(hotels_data, list):
            # リスト形式
            for hotel_data_item in hotels_data:
                # place.jsonの構造: {"hotel": [{"hotelBasicInfo": ...}, {"roomInfo": ...}]}
                if isinstance(hotel_data_item, dict) and 'hotel' in hotel_data_item:
                    hotel_array = hotel_data_item['hotel']
                    if isinstance(hotel_array, list):
                        hotel_basic_info = None
                        room_info = None

                        # hotel配列から情報を抽出
                        for item in hotel_array:
                            if isinstance(item, dict):
                                if 'hotelBasicInfo' in item:
                                    hotel_basic_info = item['hotelBasicInfo']
                                if 'roomInfo' in item:
                                    room_info = item['roomInfo']

                        if hotel_basic_info:
                            hotel_count += 1
                            format_single_hotel(hotel_basic_info, room_info, hotel_count)
                else:
                    # 従来の処理（後方互換性のため）
                    hotel_basic_info, room_info = extract_hotel_info(hotel_data_item)
                    if hotel_basic_info:
                        hotel_count += 1
                        format_single_hotel(hotel_basic_info, room_info, hotel_count)
        elif isinstance(hotels_data, dict):
            # 数値キーの辞書形式
            numeric_keys = [k for k in hotels_data.keys() if str(k).isdigit()]
            if numeric_keys:
                # 数値キーでソート
                sorted_keys = sorted(numeric_keys, key=lambda x: int(str(x)))

                for key in sorted_keys:
                    hotel_data_item = hotels_data[key]

                    # リスト形式の場合、各要素を処理
                    if isinstance(hotel_data_item, list):
                        for item in hotel_data_item:
                            hotel_basic_info, room_info = extract_hotel_info(item)
                            if hotel_basic_info:
                                hotel_count += 1
                                format_single_hotel(hotel_basic_info, room_info, hotel_count)
                                break  # 1つのホテルから1つの情報のみ取得
                    else:
                        hotel_basic_info, room_info = extract_hotel_info(hotel_data_item)
                        if hotel_basic_info:
                            hotel_count += 1
                            format_single_hotel(hotel_basic_info, room_info, hotel_count)
            else:
                # 通常のキーを持つ辞書
                for key, hotel_data_item in hotels_data.items():
                    hotel_basic_info, room_info = extract_hotel_info(hotel_data_item)
                    if hotel_basic_info:
                        hotel_count += 1
                        format_single_hotel(hotel_basic_info, room_info, hotel_count)

        else:
            st.error(f"❌ 未対応のホテルデータ構造: {type(hotels_data)}")

        if hotel_count == 0:
            st.info("🔍 ホテル情報を正しく解析できませんでした。")
            if st.session_state.get('debug_mode', False):
                st.info("デバッグモードでレスポンス構造を確認してください。")

    except Exception as e:
        # エラーが発生した場合の詳細情報
        st.error(f"❌ 結果の解析中にエラーが発生しました: {str(e)}")
        st.write("**デバッグ情報:**")

        if st.session_state.get('debug_mode', False):
            import traceback
            st.code(traceback.format_exc(), language="python")

        st.write(f"**hotels の型**: {type(results.get('hotels', 'N/A'))}")

        if results.get('hotels'):
            hotels_data = results['hotels']
            if isinstance(hotels_data, (list, dict)):
                st.write(f"**hotels の長さ**: {len(hotels_data)}")

            if isinstance(hotels_data, dict):
                keys = list(hotels_data.keys())[:5]
                st.write(f"**最初の5個のキー**: {keys}")
            elif isinstance(hotels_data, list) and len(hotels_data) > 0:
                st.write(f"**最初の要素の型**: {type(hotels_data[0])}")
                if isinstance(hotels_data[0], dict):
                    first_keys = list(hotels_data[0].keys())[:5]
                    st.write(f"**最初の要素のキー**: {first_keys}")

def main():
    st.title("🏨 楽天トラベル検索アプリ")

    # 楽天APIキーの確認
    if not RAKUTEN_APP_ID:
        st.error("⚠️ 楽天APIキーが設定されていません。.env ファイルに RAKUTEN_APP_ID を設定してください。")
        st.info("楽天ウェブサービスから Application ID を取得してください: https://webservice.rakuten.co.jp/")
    else:
        # ホテル検索フォーム
        st.subheader("🔍 ホテル検索")

        # 自然言語検索
        search_query = st.text_input(
            "検索条件を入力してください",
            placeholder="例: 東京に 12 月 1 日から 1 泊、大人 2 名で泊まれるホテル",
            help="日付、場所、人数、予算などを含めて入力してください"
        )

        if st.button("🔍 ホテルを検索") and search_query:
            with st.spinner("ホテルを検索中..."):
                if not openai.api_key:
                    st.error("⚠️ AI解析にはOpenAI APIキーが必要です")
                    params = {}
                else:
                    params = parse_travel_request_with_openai(search_query)

                # エラーチェック
                if "error" in params:
                    st.error(f"パラメータ抽出エラー: {params['error']}")
                else:
                    # AI地名選択情報の表示
                    if 'coordinate_match' in params:
                        match_info = params['coordinate_match']
                        selected_coordinates = match_info['coordinates']

                        # 使用したAPIソースを表示
                        source = selected_coordinates.get('source', 'unknown')
                        if source == 'google_geocoding':
                            source_emoji = "🌐"
                            source_text = "Google Geocoding API"
                        elif source == 'openai':
                            source_emoji = "🤖"
                            source_text = "OpenAI"
                        else:
                            source_emoji = "❓"
                            source_text = "不明"

                        #st.success(f"🎯 緯度経度選択成功（{source_emoji} {source_text}使用）: 「{match_info['original_location']}」→ 緯度: {selected_coordinates['latitude']}, 経度: {selected_coordinates['longitude']}")
                    elif params.get('coordinate_failed'):
                        st.warning("⚠️ 緯度経度の選択に失敗しました")

                    # デバッグ情報表示
                    with st.expander("🔧 検索パラメータ（デバッグ用）"):
                        st.json(params)

                    # 楽天 API 呼び出し
                    results = search_rakuten_hotels(params)

                    # 結果表示
                    format_hotel_results(results)

        # 楽天地区コードデータ表示
#        with st.expander("📍 緯度経度ベース検索について"):
#            st.markdown("""
#            **緯度経度検索の仕組み:**
#            - 入力された地名から自動的に緯度経度を取得
#            - 楽天トラベルAPIの位置ベース検索を使用
#            - 指定した地点から半径1-3km以内のホテルを検索
#
#            **検索パラメータ:**
#            - latitude: 緯度（日本測地系・秒単位）
#            - longitude: 経度（日本測地系・秒単位）
#            - searchRadius: 検索半径（1-3km）
#
#            **座標系について:**
#            - 日本測地系（Tokyo Datum）を使用
#            - 単位：秒（1度 = 3600秒）
#            - 例：東京駅 latitude=128440.51, longitude=503172.21
#            """)

        # 詳細検索オプション
        with st.expander("⚙️ 詳細検索オプション"):
            col1, col2 = st.columns(2)

            with col1:
                checkin = st.date_input("チェックイン日")
                adult_num = st.number_input("大人数", min_value=1, max_value=10, value=2)

            with col2:
                nights = st.number_input("泊数", min_value=1, max_value=30, value=1)
                max_charge = st.number_input("最大料金（円）", min_value=0, value=0, help="0の場合は制限なし")

            location_input = st.text_input(
                "地域名を入力",
                placeholder="例: 東京駅、銀座、新宿、渋谷、大阪駅",
                help="AIが地名から日本測地系の緯度経度（秒単位）を取得して位置ベース検索を行います"
            )

            search_radius = st.selectbox(
                "検索半径",
                [1, 2, 3],
                index=0,
                help="指定地点から何km以内で検索するか"
            )

            if st.button("詳細検索を実行"):
                # 詳細検索パラメータの構築
                detail_params = {
                    'checkinDate': format_date_no_padding(checkin),
                    'checkoutDate': format_date_no_padding(checkin + timedelta(days=nights)),
                    'adultNum': adult_num,
                    'searchRadius': search_radius
                }

                if max_charge > 0:
                    detail_params['maxCharge'] = max_charge

                # AI緯度経度選択
                if location_input and openai.api_key:
                    coordinates = get_coordinates_from_location(location_input)
                    if coordinates and 'latitude' in coordinates and 'longitude' in coordinates:
                        # 緯度経度をミリ秒小数点以下2桁まで丸める
                        detail_params['latitude'] = round(float(coordinates['latitude']), 2)
                        detail_params['longitude'] = round(float(coordinates['longitude']), 2)

                        # 使用したAPIソースを表示
                        source = coordinates.get('source', 'unknown')
                        if source == 'google_geocoding':
                            source_emoji = "🌐"
                            source_text = "Google Geocoding API"
                        elif source == 'openai':
                            source_emoji = "🤖"
                            source_text = "OpenAI"
                        else:
                            source_emoji = "❓"
                            source_text = "不明"

                        st.success(f"🎯 緯度経度選択（{source_emoji} {source_text}使用）: 「{location_input}」→ 緯度: {coordinates['latitude']}, 経度: {coordinates['longitude']}")
                        if 'location_name' in coordinates:
                            st.info(f"🏙️ 詳細情報: {coordinates['location_name']}")
                    else:
                        st.warning(f"⚠️ 地域「{location_input}」の緯度経度選択に失敗しました")

                with st.spinner("詳細検索を実行中..."):
                    results = search_rakuten_hotels(detail_params)
                    format_hotel_results(results)

    # サイドバーにコントロール
#    with st.sidebar:
#        st.header("⚙️ 設定")
#
#        # デバッグモード
#        debug_mode = st.checkbox("🐛 デバッグモード", value=st.session_state.get('debug_mode', False))
#        st.session_state.debug_mode = debug_mode
#
#        st.markdown("---")
#
#        # API キー状態表示
#        st.subheader("🔑 API キー状態")
#
#        if openai.api_key:
#            st.success("✅ OpenAI API キー: 設定済み")
#        else:
#            st.error("❌ OpenAI API キー: 未設定")
#
#        if RAKUTEN_APP_ID:
#            st.success("✅ 楽天 API キー: 設定済み")
#        else:
#            st.error("❌ 楽天 API キー: 未設定")
#
#        st.markdown("---")
#        st.markdown("### 📖 使用方法")
#        st.markdown("**ホテル検索:**")
#        st.markdown("- 自然な文章でホテル検索条件を入力")
#        st.markdown("- AI が地名から日本測地系の緯度経度を取得")
#        st.markdown("- 位置ベース検索で周辺ホテルを検索")
#
#        st.markdown("---")
#
#        # place.jsonテスト機能
#        st.subheader("🧪 place.jsonテスト")
#        if st.button("place.jsonをテスト"):
#            try:
#                with open('place.json', 'r', encoding='utf-8') as f:
#                    place_data = json.load(f)
#                st.success("place.jsonの読み込みに成功しました")
#
#                # place.jsonの内容をformat_hotel_resultsでフォーマット
#                formatted_results = format_hotel_results(place_data)
#                st.markdown("### 📋 place.jsonのフォーマット結果:")
#                st.markdown(formatted_results)
#
#            except FileNotFoundError:
#                st.error("place.jsonファイルが見つかりません")
#            except Exception as e:
#                st.error(f"place.jsonの処理中にエラーが発生しました: {str(e)}")

#        st.markdown("---")

if __name__ == "__main__":
    main()
