import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta, time
import streamlit.components.v1 as components
from io import BytesIO
import re

# --- 1. 페이지 설정 및 초기화 ---
st.set_page_config(layout="wide", page_title="B787-9 Rotation (Final)")
st.title("✈️ AC Rotation Scheduler")

BASE_DATE = datetime(2024, 1, 1)

if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
if 'custom_resources' not in st.session_state:
    st.session_state.custom_resources = []
if 'deleted_resources' not in st.session_state:
    st.session_state.deleted_resources = []

# --- 2. 헬퍼 함수 ---
def parse_d_time(d_str):
    try:
        if pd.isna(d_str): return BASE_DATE
        d_str = str(d_str).strip()
        parts = d_str.split()
        if len(parts) < 2: return BASE_DATE
        day_match = re.search(r'\d+', parts[0])
        day_offset = int(day_match.group()) - 1 if day_match else 0
        time_part = parts[1].replace(":", "")
        return BASE_DATE + timedelta(days=day_offset, hours=int(time_part[:2]), minutes=int(time_part[2:]))
    except:
        return BASE_DATE

def format_d_time(dt):
    if pd.isna(dt): return ""
    if dt.tzinfo is not None: dt = dt.tz_localize(None)
    diff = dt - BASE_DATE
    day_num = (diff.days % 7) + 1
    return f"D{day_num} {dt.hour:02d}{dt.minute:02d}"

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

# --- 3. 최적화 알고리즘 함수 ---
def run_optimization(df):
    if df.empty: return df
    df_opt = df.copy()
    
    # 1. 시작 시간(Start) 우선, 그 다음 종료 시간(End) 순으로 정렬
    df_opt = df_opt.sort_values(by=['Start', 'End'])
    
    lanes_end_times = [] # 각 Lane의 마지막 스케줄 종료 시간 추적
    
    for idx, row in df_opt.iterrows():
        start = row['Start']
        end = row['End']
        assigned_lane_index = -1
        
        # 2. 기존 Lane들을 순회하며 들어갈 수 있는(겹치지 않는) 첫 번째 공간 탐색
        for i, last_end in enumerate(lanes_end_times):
            if start >= last_end: 
                assigned_lane_index = i
                lanes_end_times[i] = end 
                break
        
        # 3. 들어갈 공간이 없으면 새로운 Lane 추가
        if assigned_lane_index == -1:
            lanes_end_times.append(end)
            assigned_lane_index = len(lanes_end_times) - 1
        
        # 4. Resource 이름 재할당 (#1, #2, ...)
        res_name = f"#{assigned_lane_index + 1}"
        df_opt.at[idx, 'Resource'] = res_name
        
    # 5. 세션 상태 업데이트: 필요한 Lane 수에 맞춰 Custom Resources 정리
    # 기본 8개(#1~#8)를 초과하는 Lane만 custom_resources에 등록
    max_lane = len(lanes_end_times)
    new_custom = []
    if max_lane > 8:
        for i in range(9, max_lane + 1):
            new_custom.append(f"#{i}")
    
    st.session_state.custom_resources = new_custom
    
    # 최적화 후에는 모든 Lane이 보여야 하므로 삭제 목록 초기화
    st.session_state.deleted_resources = []
    
    return df_opt

# --- 4. 데이터 로드 ---
def load_data(uploaded_file):
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
    else:
        df = pd.DataFrame([
            {"Resource": "#1", "Start_D": "D1 1320", "End_D": "D2 1620", "Label": "LAX", "Color": "#FFB6C1"},
            {"Resource": "#2", "Start_D": "D1 2155", "End_D": "D2 0540", "Label": "EWR", "Color": "#ADD8E6"},
        ])
    for col, default in [('Color', '#ADD8E6'), ('Resource', 'Unassigned'), ('Label', 'Flight')]:
        if col not in df.columns: df[col] = default
    if 'Start_D' in df.columns:
        df['Start'] = df['Start_D'].apply(parse_d_time)
        df['End'] = df['End_D'].apply(parse_d_time)
    return df

# --- 5. 사이드바 설정 ---
st.sidebar.header("1. 데이터 파일")
uploaded_file = st.sidebar.file_uploader("엑셀 업로드", type=["xlsx"])
if st.session_state.schedule_df is None or uploaded_file is not None:
    if uploaded_file:
        st.session_state.schedule_df = load_data(uploaded_file)
    elif st.session_state.schedule_df is None:
        st.session_state.schedule_df = load_data(None)

st.sidebar.markdown("---")
st.sidebar.header("2. 기재(Row) 관리")
if st.sidebar.button("🚀 Optimizer", type="primary"):
    if st.session_state.schedule_df is not None and not st.session_state.schedule_df.empty:
        optimized_df = run_optimization(st.session_state.schedule_df)
        st.session_state.schedule_df = optimized_df
        st.toast("최적화 완료!", icon="✅")
        st.rerun()

with st.sidebar.expander("➕ 기재(Row) 추가", expanded=False):
    new_row_name = st.text_input("추가할 기재 이름")
    if st.button("추가 확인"):
        if new_row_name:
            if new_row_name not in st.session_state.custom_resources:
                st.session_state.custom_resources.append(new_row_name)
            if new_row_name in st.session_state.deleted_resources:
                st.session_state.deleted_resources.remove(new_row_name)
            st.rerun()

base_resources = [f"#{i}" for i in range(1, 9)]
existing = st.session_state.schedule_df['Resource'].unique().tolist()
custom = st.session_state.custom_resources
candidates = list(set(base_resources + existing + custom))
all_resources = sorted(
    [r for r in candidates if r not in st.session_state.deleted_resources], 
    key=natural_sort_key
)

with st.sidebar.expander("➖ 기재(Row) 제거", expanded=False):
    del_target = st.selectbox("제거할 기재 선택", options=all_resources)
    if st.button("제거 확인"):
        if del_target:
            st.session_state.deleted_resources.append(del_target)
            if del_target in st.session_state.custom_resources:
                st.session_state.custom_resources.remove(del_target)
            st.session_state.schedule_df = st.session_state.schedule_df[
                st.session_state.schedule_df['Resource'] != del_target
            ]
            st.rerun()

st.sidebar.markdown("---")
st.sidebar.header("3. 스케줄 추가")
with st.sidebar.form("add_task_form", clear_on_submit=True):
    c1, c2 = st.columns(2)
    with c1:
        f_res = st.selectbox("기재", all_resources)
        f_lbl = st.text_input("목적지", "ICN-LAX")
        f_col = st.color_picker("색상", "#90EE90")
    with c2:
        f_day = st.selectbox("출발일", [f"D{i}" for i in range(1,8)])
        f_time = st.time_input("출발시간", time(10,0))
        dur_h = st.number_input("시간(H)", 0, 24, 10)
        dur_m = st.number_input("분(M)", 0, 59, 0, 10)
    if st.form_submit_button("➕ 추가하기"):
        day_off = int(f_day[1:]) - 1
        s_dt = BASE_DATE + timedelta(days=day_off, hours=f_time.hour, minutes=f_time.minute)
        e_dt = s_dt + timedelta(hours=dur_h, minutes=dur_m)
        new_row = pd.DataFrame([{
            "Resource": f_res, "Label": f_lbl, "Color": f_col,
            "Start_D": format_d_time(s_dt), "End_D": format_d_time(e_dt),
            "Start": s_dt, "End": e_dt
        }])
        st.session_state.schedule_df = pd.concat([st.session_state.schedule_df, new_row], ignore_index=True)
        st.rerun()

# --- 6. 메인 화면 ---
st.subheader("📊 클릭하여 선택 → 삭제/복제 → Save)")

# --- 7. 시각화 데이터 준비 ---
final_df = st.session_state.schedule_df.copy()
final_df = final_df[final_df['Resource'].isin(all_resources)]

groups = [{"id": res, "content": f"<b>{res}</b>", "order": i} for i, res in enumerate(all_resources)]
items = []
for i, row in final_df.iterrows():
    if pd.isna(row['Start']) or pd.isna(row['End']): continue
    c_val = row['Color'] if not pd.isna(row['Color']) else '#ADD8E6'
    items.append({
        "id": i, "group": row['Resource'], "content": str(row['Label']),
        "start": row['Start'].isoformat(), "end": row['End'].isoformat(),
        "style": f"background-color: {c_val}; border-color: black;"
    })

# --- 8. Vis.js 타임라인 (삭제/복제 JS 로직 추가) ---
html_code = f"""
<!DOCTYPE html>
<html>
<head>
  <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.2/vis-timeline-graph2d.min.js"></script>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.2/vis-timeline-graph2d.min.css" rel="stylesheet" type="text/css" />
  <script src="https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js"></script>
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background-color: white; margin: 0; }}
    #visualization {{ border: 1px solid #ddd; height: 600px; width: 100%; }}
    .vis-time-axis .vis-text {{ font-weight: bold; color: #333; }}
    .vis-item.vis-selected {{ border-color: red; border-width: 2px; box-shadow: 0 0 10px rgba(0,0,0,0.5); }} /* 선택 시 강조 */
    
    .btn-group {{ margin-top: 10px; display: flex; gap: 10px; }}
    .btn {{ padding: 10px 15px; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold; }}
    
    .btn-save {{ background-color: #008CBA; }}
    .btn-img {{ background-color: #4CAF50; }}
    .btn-del {{ background-color: #f44336; }} /* 빨강 */
    .btn-dup {{ background-color: #FF9800; }} /* 주황 */
    .btn:hover {{ opacity: 0.9; }}
  </style>
</head>
<body>
<div id="visualization"></div>

<div class="btn-group">
    <button class="btn btn-del" onclick="deleteSelected()">🗑️ 선택 삭제 (Delete)</button>
    <button class="btn btn-dup" onclick="duplicateSelected()">📑 선택 복제 (Duplicate)</button>
    <button class="btn btn-save" onclick="saveData()">💾 Save Position</button>
    <button class="btn btn-img" onclick="captureImage()">📸 이미지 저장</button>
</div>
<div id="msg" style="color: blue; margin-top: 5px; font-weight: bold; height: 20px;"></div>

<script>
  var timeline, items, container = document.getElementById('visualization');

  function toLocalIsoString(date) {{
      var dt = new Date(date);
      var localDt = new Date(dt.getTime() - (dt.getTimezoneOffset() * 60000));
      return localDt.toISOString().slice(0, 19); 
  }}

  // [NEW] 선택 항목 삭제 함수
  function deleteSelected() {{
    var selection = timeline.getSelection();
    if (selection.length === 0) {{
        alert("먼저 삭제할 Bar를 클릭해서 선택해주세요.");
        return;
    }}
    if (confirm("선택한 스케줄을 삭제하시겠습니까?")) {{
        items.remove(selection);
        document.getElementById('msg').innerText = "🗑️ 삭제되었습니다. 'Save Position'을 눌러 확정하세요.";
    }}
  }}

  // [NEW] 선택 항목 복제 함수
  function duplicateSelected() {{
    var selection = timeline.getSelection();
    if (selection.length === 0) {{
        alert("복제할 Bar를 클릭해서 선택해주세요.");
        return;
    }}
    
    var id = selection[0];
    var item = items.get(id);
    
    // 복제본 생성
    var newItem = JSON.parse(JSON.stringify(item)); // Deep Copy
    newItem.id = new Date().getTime(); // 유니크 ID 생성 (현재시간 밀리초)
    newItem.content = item.content + " (Copy)";
    
    // 약간 뒤로 이동시켜서 겹침 방지 (1시간 뒤)
    var startDt = new Date(item.start);
    var endDt = new Date(item.end);
    startDt.setHours(startDt.getHours() + 1);
    endDt.setHours(endDt.getHours() + 1);
    
    newItem.start = startDt;
    newItem.end = endDt;
    
    items.add(newItem);
    timeline.setSelection(newItem.id); // 새로 생긴 것 선택
    document.getElementById('msg').innerText = "📑 복제되었습니다. 'Save Position'을 눌러 확정하세요.";
  }}

  function saveData() {{
    if (!items) return;
    var data = items.get();
    var simpl = data.map(function(item) {{
        return {{ 
            "Resource": item.group, 
            "Start_ISO": toLocalIsoString(item.start), 
            "End_ISO": toLocalIsoString(item.end), 
            "Label": item.content, 
            "Color": item.style ? item.style.split(';')[0].split(':')[1].trim() : '#ADD8E6' 
        }};
    }});
    navigator.clipboard.writeText(JSON.stringify(simpl)).then(function() {{
        document.getElementById('msg').innerHTML = "✅ <b>데이터 복사 완료!</b> 하단에 붙여넣고 업데이트 하세요.";
    }}).catch(function(err) {{
        alert("복사 실패: " + err);
    }});
  }}

  async function captureImage() {{
    var msg = document.getElementById('msg');
    msg.innerText = "⏳ 1000px 전체 캡처 중...";
    var originalWidth = container.style.width;
    try {{
        container.style.width = "1000px";
        timeline.setOptions({{ width: '1000px' }});
        timeline.setWindow('2024-01-01 00:00:00', '2024-01-08 00:00:00', {{animation: false}});
        timeline.redraw();
        await new Promise(r => setTimeout(r, 1000));
        const canvas = await html2canvas(container, {{ scale: 2, backgroundColor: "#ffffff", width: 1000, windowWidth: 1000, useCORS: true }});
        var link = document.createElement('a');
        link.download = 'Rotation_Schedule.png';
        link.href = canvas.toDataURL("image/png");
        document.body.appendChild(link); link.click(); document.body.removeChild(link);
        msg.innerText = "✅ 이미지 저장 완료!";
    }} catch(err) {{ alert("오류: " + err.message); }} 
    finally {{
        container.style.width = originalWidth;
        timeline.setOptions({{ width: '100%' }});
        timeline.setWindow('2024-01-01 00:00:00', '2024-01-08 00:00:00', {{animation: false}});
        setTimeout(() => {{ msg.innerText = ""; }}, 3000);
    }}
  }}

  try {{
      var groups = new vis.DataSet({json.dumps(groups)});
      items = new vis.DataSet({json.dumps(items)});
      var options = {{
        groupOrder: 'order', editable: true, stack: false, margin: {{ item: 5, axis: 5 }}, orientation: 'top',
        min: '2024-01-01 00:00:00', max: '2024-01-08 00:00:00',
        start: '2024-01-01 00:00:00', end: '2024-01-08 00:00:00',
        zoomMin: 1000 * 60 * 60 * 6, zoomMax: 1000 * 60 * 60 * 24 * 7,
        format: {{
          minorLabels: function(date, scale, step) {{ return new Date(date).getHours() + 'h'; }},
          majorLabels: function(date, scale, step) {{ return 'D' + new Date(date).getDate(); }}
        }},
        snap: function (date, scale, step) {{ var m = 10 * 60 * 1000; return Math.round(date / m) * m; }}
      }};
      timeline = new vis.Timeline(container, items, groups, options);
  }} catch (err) {{ container.innerHTML = "Error: " + err.message; }}
</script>
</body>
</html>
"""
components.html(html_code, height=730)

# --- 9. 데이터 업데이트 ---
st.markdown("---")
st.subheader("📥 변경사항 확정 (Update)")
with st.form("save_form"):
    st.info("차트 변경사항(이동/삭제/복제)이 있다면 **'💾 Save Position'** 버튼을 누른 뒤, 이곳에 **Ctrl+V**로 붙여넣으세요.")
    json_input = st.text_area("데이터 붙여넣기", height=100, label_visibility="collapsed")
    submitted = st.form_submit_button("✅ 스케줄 업데이트 및 고정")
    if submitted and json_input:
        try:
            new_data = json.loads(json_input)
            processed_rows = []
            for row in new_data:
                s_dt = pd.to_datetime(row['Start_ISO'])
                e_dt = pd.to_datetime(row['End_ISO'])
                if s_dt.tzinfo is not None: s_dt = s_dt.tz_localize(None)
                if e_dt.tzinfo is not None: e_dt = e_dt.tz_localize(None)
                processed_rows.append({
                    "Resource": row['Resource'],
                    "Start_D": format_d_time(s_dt), "End_D": format_d_time(e_dt),
                    "Label": row['Label'], "Color": row['Color'],
                    "Start": s_dt, "End": e_dt
                })
            updated_df = pd.DataFrame(processed_rows)
            updated_df = updated_df[updated_df['Resource'].isin(all_resources)]
            st.session_state.schedule_df = updated_df
            st.success("스케줄이 성공적으로 업데이트되었습니다!")
            st.rerun()
        except Exception as e:
            st.error(f"데이터 형식이 올바르지 않습니다: {e}")

# --- 10. 엑셀 다운로드 ---
if not st.session_state.schedule_df.empty:
    with st.expander("📊 엑셀 파일 다운로드"):
        export_df = st.session_state.schedule_df.copy()
        export_df['Resource'] = pd.Categorical(export_df['Resource'], categories=all_resources, ordered=True)
        export_df = export_df.sort_values('Resource')
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()
        st.download_button("📥 전체 스케줄 엑셀 다운로드", to_excel(export_df), 'schedule_final.xlsx')