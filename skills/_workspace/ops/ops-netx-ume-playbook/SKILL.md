---
name: ops-netx-ume-playbook
description: 闈㈠悜 ops 涓撳鐨?netx UME 杩愮淮浣滀笟鎵嬪唽銆傝鐩栧憡璀︽煡璇?鑱氬悎/璇婃柇銆佺綉鍏冩竻鍗曚笌鍗曠綉鍏冭鎯呫€乺aw 瀛楁杩囨护涓?UME 鍙 SQL銆?---

# Ops Netx UME 浣滀笟鎵嬪唽

## 寮哄埗浣跨敤鑼冨洿

鍑℃槸娑夊強 netx/UME **鍛婅**鎴?**缃戝厓淇℃伅** 鐨?ops 璇锋眰锛屽繀椤讳紭鍏堝姞杞藉苟閬靛惊鏈妧鑳姐€?
## 宸ュ叿閫夋嫨椤哄簭

1. 鍩虹瑙嗗浘锛堝厛鐪嬫暣浣擄級锛?   - `netx_query_ume_alarms`
   - `netx_aggregate_ume_alarms`
   - `netx_run_ume_diagnostics`
2. 瀛楁鎰熺煡娣辨煡锛堥渶瑕佺粏鑺傦級锛?   - `netx_list_ume_alarm_fields`
   - `netx_query_ume_alarms_raw`锛堜紭鍏堜娇鐢?`select_fields` 鎺у埗杩斿洖瀛楁锛?3. 鑷畾涔夎仛鍚堬紙闈?SQL锛夛細
   - `netx_aggregate_ume_alarms_raw`锛坄group_by`锛屽彲閫?`group_by2`锛?4. 楂樼骇鍒嗘瀽锛圫QL锛夛細
   - `netx_sql_query_ume`锛堜粎 SELECT銆佷粎 UME 琛紱閲嶆煡璇㈠缓璁缃?`statement_timeout_ms`锛?5. **缃戝厓锛坕nventory锛屼笌 netx銆岀綉鍏冩竻鍗曘€嶅悓婧愶級**锛?   - 鍒楄〃/鎼滅储锛歚netx_query_ume_ne_inventory`锛坄keyword` + 鍒嗛〉锛?   - 鍗曟潯璇︽儏锛堝惈 `raw_json`锛夛細`netx_get_ume_ne`锛坄ne_id` = UUID锛?
## 蹇€熷喅绛栨爲锛堝己鎺ㄨ崘锛?
- **鍙渶瑕佹暣浣撴€佸娍 / Top 椋庨櫓 / 蹇€熺畝鎶?*锛?  - 鍏?`netx_aggregate_ume_alarms` + `netx_run_ume_diagnostics`
  - 蹇呰鏃跺啀鐢?`netx_query_ume_alarms` 鐪嬪墠 1 椤靛仛鏍锋湰鏍稿
- **闇€瑕佲€滃彲寮曠敤璇佹嵁鈥濈殑鍏蜂綋鍛婅鏄庣粏**锛?  - 鍏?`netx_list_ume_alarm_fields`
  - 鍐?`netx_query_ume_alarms_raw`锛屽苟鐢?`select_fields` 鍙彇蹇呰瀛楁
- **闇€瑕佹寜浠绘剰瀛楁鍋氱粺璁★紙浣嗕笉鎯冲啓 SQL锛?*锛?  - `netx_aggregate_ume_alarms_raw`锛坄group_by` / `group_by2`锛?- **闇€瑕佸鏉傛潯浠?/ 鑷畾涔夎绠?/ 澶氭潯浠跺叧鑱?*锛?  - `netx_sql_query_ume`锛堝繀椤昏繃婊?+ `statement_timeout_ms`锛?- **鏌ョ綉鍏冩槸璋併€両P/鏍囩銆佸湪绾跨姸鎬併€佹垨鏍稿鍛婅閲岀殑 ne_id**锛?  - 鍏?`netx_query_ume_ne_inventory`锛坄keyword` 鍙～鍚嶇О銆佷富鏈哄悕銆佹爣绛俱€両P 鎴?UUID 鐗囨锛?  - 闇€瑕佸畬鏁村瓧娈典笌 `raw_json` 鏃跺啀 `netx_get_ume_ne`

## 绾︽潫涓庢姢鏍?
- 浼樺厛浣跨敤闈?SQL 宸ュ叿锛涗粎褰撳伐鍏峰弬鏁版棤娉曡〃杈鹃渶姹傛椂鍐嶇敤 SQL銆?- 榛樿杩囨护浼樺厛绾э紙鍏堟敹鏁涘啀鎵╁睍锛夛細
  - 棣栭€夛細`severity`锛堝厛鎶婇棶棰樼缉灏忓埌 critical/major 绛夛級
  - 鍏舵锛歚keyword`锛堢綉鍏冨悕/鏍囩/IP/瀵硅薄鍚?鍛婅鍏抽敭瀛楋級
  - 鍐嶆锛歚time_from/time_to`锛堟寜 `last_seen_at` 闄愬畾鏃堕棿绐楋級
  - 鏈€鍚庯細`event_type` 鎴?`ne_id`锛堝綋浣犳槑纭煡閬撹閿佸畾浜嬩欢绫诲瀷/缃戝厓鏃讹級
- 绂佹鈥滀负浜嗗噾鍏ㄩ噺鑰屾棤鑴戠炕椤碘€濓細
  - `netx_query_ume_alarms` 榛樿鍙湅鍓?1 椤碉紙蹇呰鏃舵渶澶?2 椤碉級
  - 濡傞渶鏇村鏁版嵁锛屽繀椤诲厛鏄庣‘杩囨护鏉′欢锛坄severity/ne_id/keyword/time_from/time_to/event_type` 绛夛級鎴栨敼鐢ㄨ仛鍚?SQL
- 鎺у埗鍝嶅簲浣撶Н锛?  - 榛樿 `page_size=50`锛堥櫎闈炴槑纭渶瑕佹洿澶氾紝鍚﹀垯涓嶈涓婃潵灏辨媺婊?500锛?  - 鍔ㄦ€佽仛鍚堥粯璁?`limit=200`
  - 鍚堢悊璁剧疆 `page_size`
  - raw 鏌ヨ灏介噺浼?`select_fields`锛涙垨浣跨敤 `field_preset=brief/evidence/ne_debug`
  - 鍏堝姞杩囨护鏉′欢锛屽啀澧炲ぇ鍒嗛〉鑼冨洿
- 鏃堕棿绐楄繃婊ら粯璁ゅ熀浜?`last_seen_at` 璇箟锛岄櫎闈為渶姹傛槑纭姹傚叾瀹冨彛寰勩€?- 鑻ユ暟鎹柊椴滃害涓嶆槑纭紝鍏堟煡鐪?runtime 閿氱偣鐘舵€侊紝鍐嶄笅缁撹銆?- SQL 浣跨敤瑙勫垯锛坄netx_sql_query_ume`锛夛細
  - 寤鸿鎬绘槸璁剧疆 `statement_timeout_ms`锛堜緥濡?3000~10000锛?  - 鎺ㄨ崘榛樿浠?`statement_timeout_ms=8000` 寮€濮?  - 闄ら潪鍙槸 `count(*)`锛屽惁鍒欏簲鍖呭惈杩囨护鏉′欢锛堣嚦灏戞椂闂寸獥鎴?`ne_id`/涓ラ噸搴﹁繃婊わ級锛岄伩鍏嶅叏琛ㄦ壂鎻?
## 杈撳嚭绾﹀畾

- 杈撳嚭蹇呴』鍖呭惈锛?  - 绠€鏄庣粨璁?  - 璇佹嵁渚濇嵁锛堝伐鍏疯緭鍑猴級
  - 鍙墽琛屼笅涓€姝?- 娌℃湁宸ュ叿璇佹嵁鏃讹紝涓嶅緱鑷嗘祴鍛婅浜嬪疄銆?- **鐢ㄦ埛鐢ㄨ嫳鏂囨彁闂椂锛堝己鍒讹級**锛氬洖澶嶄腑**涓嶅緱鍑虹幇浠讳綍姹夊瓧**锛涘伐鍏烽噷鐨勪腑鏂囧憡璀﹀瓧娈碉紙鍘熷洜銆佸璞″悕銆佹弿杩扮瓑锛夊繀椤诲厛**璇戞垚鑻辨枃**鍐嶅啓鍏ヨ〃鏍兼垨姝ｆ枃锛岀姝㈠師鏍风矘璐达紱缃戝厓鍚嶇敤 `host_name`锛屽崗璁被缁村害鐢ㄨ嫳鏂囩被鍒悕锛圤ther/Clock/鈥︼級銆?
### 缃戝厓灞曠ず锛氫互 host_name 涓轰富閿紙寮哄埗锛?
- **鍛婅/缁熻閲屾爣璇嗙綉鍏冩椂锛屼富閿案杩滄槸 `host_name`**锛堜富鏈哄悕锛夛紝涓嶆槸 `ne_id`銆傝〃鏍肩涓€鍒椼€乀op 缃戝厓銆佸垎缁勯敭銆佺粨璁洪噷鐨勭綉鍏冨悕閮界敤瀹冦€?- **浼樺厛鏁版嵁婧?*锛堝悓姝ユ椂宸插啓鍏ュ憡璀﹁〃锛夛細
  - `netx_query_ume_alarms` 鈫?瀛楁 **`host_name`**
  - `netx_query_ume_alarms_raw` 鈫?**`alarm_host_name`**锛坄select_fields` / `brief` / `evidence` 棰勮宸插寘鍚級
  - 鑱氬悎 鈫?`group_by=alarm_host_name` 鎴?`group_by=ne_host_name`
- **绂佹**瀵圭敤鎴峰睍绀鸿８ `ne_id` / `alarm_ne_id`锛沗ne_id` 浠呬綔鏌ヨ鍙傛暟銆?- `host_name` 涓虹┖鏃讹細鐢?`user_label` / `ne_name` 骞舵敞鏄庣己澶憋紱浠嶄笉寰楅€€鍥?UUID銆?- 浠呭綋鍒楄〃鎺ュ彛缂?`host_name` 鏃跺啀 `netx_get_ume_ne` / 缃戝厓娓呭崟 / SQL JOIN 琛ュ叏銆?
## 鎺ㄨ崘鍒嗘瀽妯″紡

- 楂橀闄╃綉鍏冿細`netx_aggregate_ume_alarms_raw` + `group_by=alarm_host_name`锛堥閫夛級鎴?`ne_host_name` + 涓ラ噸搴﹁繃婊わ紱鍕挎寜 `alarm_ne_id` 鍒嗙粍瀵瑰灞曠ず銆?- 涓ラ噸搴﹀垎甯冿細`group_by=alarm_perceived_severity`銆?- 浜嬩欢瓒嬪娍鍒囩墖锛歳aw 鏌ヨ涓粍鍚?`time_from/time_to` + `event_type`銆?
## 鍙傝€冩ā鏉?
- 蹇€熸ā鏉胯锛歔reference.md](reference.md)
