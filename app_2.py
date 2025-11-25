import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta, time
import streamlit.components.v1 as components
from io import BytesIO
import re

# --- 1. 페이지 설정 및 세션 초기화 ---
st.set_page_config(layout="wide", page_title="B787-9 Rotation (D1-D7)")
st.title("✈️ B787-9 Rotation Scheduler (Row 추가 기능 포함)")

# 기준일: 내부 계산용
BASE_DATE = datetime(2024, 1, 1)

# 세션 상태 초기화 (새로고침 해도 데이터 유지)
if 'new_tasks_list' not in st.session_state:
    st.session_state.new_tasks_list = []
if 'custom_resources' not in st.session_state: # [NEW] 사용자 추가 Row 저장소
    st.session_state.custom_resources = []

# --- 2. 헬퍼 함수 (D-Day 변환) ---
def parse_d_time(d_str):
    """ 'D1 1320' -> datetime 변환 """
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
    """ datetime -> 'D1 1320' 변환 """
    if pd.isna(dt): return ""
    diff = dt - BASE_DATE
    day_num = (diff.days % 7) + 1
    return f"D{day_num} {dt.hour:02d}{dt.minute:02d}"

# --- 3. 데이터 로드 ---
def create_sample_data():
    return pd.DataFrame([
        {"Resource": "#1", "Start_D": "D1 1320", "End_D": "D2 1620", "Label": "LAX", "Color": "#FFB6C1"},
        {"Resource": "#2", "Start_D": "D1 2155", "End_D": "D2 0540", "Label": "EWR", "Color": "#ADD8E6"},
    ])

st.sidebar.header("1. 데이터 파일 (엑셀)")
uploaded_file = st.sidebar.file_uploader("업로드 (.xlsx)", type=["xlsx"])

if uploaded_file:
    df_original = pd.read_excel(uploaded_file)
else:
    df_original = create_sample_data()

# [안전장치] 필수 컬럼 자동 생성
if 'Color' not in df_original.columns: df_original['Color'] = '#ADD8E6'
if 'Resource' not in df_original.columns: df_original['Resource'] = 'Unassigned'
if 'Label' not in df_original.columns: df_original['Label'] = 'Flight'

# Start/End 계산
if 'Start_D' in df_original.columns:
    df_original['Start'] = df_original['Start_D'].apply(parse_d_time)
    df_original['End'] = df_original['End_D'].apply(parse_d_time)

# --- [NEW] 4. Row(기재) 관리 및 리스트 통합 ---
st.sidebar.markdown("---")
st.sidebar.header("2. 기재(Row) 관리")

# 2-1. Row 추가 메뉴
with st.sidebar.expander("➕ 새 기재(Row) 추가하기", expanded=False):
    new_row_name = st.text_input("기재 이름 (예: #9, #Extra)")
    if st.button("Row 추가"):
        if new_row_name and new_row_name not in st.session_state.custom_resources:
            st.session_state.custom_resources.append(new_row_name)
            st.success(f"'{new_row_name}' 추가됨!")
            st.rerun() # 화면 새로고침해서 바로 반영
        elif new_row_name in st.session_state.custom_resources:
            st.warning("이미 존재하는 이름입니다.")

# 2-2. 전체 리소스 리스트 생성 (기본 + 엑셀 + 사용자추가)
base_resources = [f"#{i}" for i in range(1, 9)]
existing_from_excel = df_original['Resource'].unique().tolist()
custom_added = st.session_state.custom_resources

# 중복 제거 및 정렬
all_resources = sorted(list(set(base_resources + existing_from_excel + custom_added)))


# --- 5. 스케줄(Task) 추가 ---
st.sidebar.markdown("---")
st.sidebar.header("3. 스케줄(Bar) 추가")
with st.sidebar.form("add_task"):
    c1, c2 = st.columns(2)
    with c1:
        # 여기서 all_resources를 쓰므로 방금 추가한 Row도 선택 가능
        n_res = st.selectbox("기재 선택", all_resources)
        n_lbl = st.text_input("목적지", "ICN-LAX")
        n_col = st.color_picker("색상", "#90EE90")
    with c2:
        n_day = st.selectbox("출발일", [f"D{i}" for i in range(1,8)])
        n_time = st.time_input("출발시간", time(10,0))
        dur_h = st.number_input("시간(H)", 0, 24, 10)
        dur_m = st.number_input("분(M)", 0, 59, 0, 10)
    
    if st.form_submit_button("➕ 스케줄 추가"):
        day_off = int(n_day[1:]) - 1
        s_dt = BASE_DATE + timedelta(days=day_off, hours=n_time.hour, minutes=n_time.minute)
        e_dt = s_dt + timedelta(hours=dur_h, minutes=dur_m)
        
        st.session_state.new_tasks_list.append({
            "Resource": n_res, "Label": n_lbl, "Color": n_col,
            "Start": s_dt, "End": e_dt,
            "Start_D": format_d_time(s_dt), "End_D": format_d_time(e_dt)
        })
        st.success("추가됨!")

# --- 6. 데이터 병합 ---
if st.session_state.new_tasks_list:
    df_new = pd.DataFrame(st.session_state.new_tasks_list)
    df_combined = pd.concat([df_original, df_new], ignore_index=True)
else:
    df_combined = df_original.copy()

# 데이터 테이블 보기
with st.expander("📊 데이터 테이블 보기 (Click)", expanded=False):
    cols = [c for c in ['Resource', 'Start_D', 'End_D', 'Label', 'Color'] if c in df_combined.columns]
    st.dataframe(df_combined[cols])

# --- 7. JSON 변환 ---
# [중요] Row(Group) 데이터 생성 시 all_resources를 사용해야 빈 Row도 차트에 나옴
groups = [{"id": res, "content": f"<b>{res}</b>"} for res in all_resources]

items = []
for i, row in df_combined.iterrows():
    color_val = row['Color'] if not pd.isna(row['Color']) else '#ADD8E6'
    items.append({
        "id": i,
        "group": row['Resource'],
        "content": row['Label'],
        "start": row['Start'].isoformat(),
        "end": row['End'].isoformat(),
        "style": f"background-color: {color_val}; border-color: black;"
    })

# --- 8. HTML/JS (D1~D7 고정 타임라인) ---
html_code = f"""
<!DOCTYPE html>
<html>
<head>
  <script type="text/javascript" src="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.2/vis-timeline-graph2d.min.js"></script>
  <link href="https://cdnjs.cloudflare.com/ajax/libs/vis-timeline/7.7.2/vis-timeline-graph2d.min.css" rel="stylesheet" type="text/css" />
  <style>
    body {{ font-family: 'Segoe UI', sans-serif; background-color: white; margin: 0; }}
    #visualization {{ border: 1px solid #ddd; height: 600px; }}
    .vis-time-axis .vis-text {{ font-weight: bold; color: #333; }}
    .vis-time-axis .vis-text.vis-major {{ color: #000; font-size: 14px; }}
    .vis-item {{ border-width: 1px; font-weight: bold; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
    .btn-copy {{ margin-top: 10px; padding: 10px 20px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; }}
  </style>
</head>
<body>
<div id="visualization"></div>
<button class="btn-copy" onclick="exportData()">💾 결과 복사</button>
<span id="msg" style="color: green; margin-left: 10px;"></span>
<script>
  try {{
      var groups = new vis.DataSet({json.dumps(groups)});
      var items = new vis.DataSet({json.dumps(items)});
      var container = document.getElementById('visualization');
      
      var options = {{
        groupOrder: 'content', 
        editable: true, 
        stack: false, 
        margin: {{ item: 5, axis: 5 }},
        orientation: 'top',
        
        min: '2024-01-01 00:00:00',
        max: '2024-01-08 00:00:00',
        start: '2024-01-01 00:00:00',
        end: '2024-01-08 00:00:00',
        
        zoomMin: 1000 * 60 * 60 * 6,
        zoomMax: 1000 * 60 * 60 * 24 * 7,
        
        format: {{
          minorLabels: function(date, scale, step) {{
            var dt = new Date(date);
            return dt.getHours() + 'h';
          }},
          majorLabels: function(date, scale, step) {{
            var dt = new Date(date);
            var d = dt.getDate(); 
            return 'D' + d; 
          }}
        }},
        
        snap: function (date, scale, step) {{ var m = 10 * 60 * 1000; return Math.round(date / m) * m; }}
      }};

      var timeline = new vis.Timeline(container, items, groups, options);
      
      function exportData() {{
        var data = items.get();
        var simpl = data.map(function(item) {{
            return {{ "Resource": item.group, "Start_ISO": item.start, "End_ISO": item.end, "Label": item.content, 
                      "Color": item.style ? item.style.split(';')[0].split(':')[1].trim() : '#ADD8E6' }};
        }});
        navigator.clipboard.writeText(JSON.stringify(simpl)).then(function() {{
            document.getElementById('msg').innerText = "복사 완료! 하단에 붙여넣으세요.";
        }});
      }}
  }} catch (err) {{
      document.getElementById('visualization').innerHTML = "ERROR: " + err.message;
  }}
</script>
</body>
</html>
"""

st.subheader("4. 인터랙티브 스케줄러 (D1 ~ D7)")
components.html(html_code, height=650)

# --- 9. 저장 ---
st.markdown("---")
st.subheader("5. 결과 저장")
json_input = st.text_area("복사한 데이터 붙여넣기 (Ctrl+V)", height=100)

if json_input:
    try:
        new_data = json.loads(json_input)
        processed_rows = []
        for row in new_data:
            s_dt = pd.to_datetime(row['Start_ISO'])
            e_dt = pd.to_datetime(row['End_ISO'])
            processed_rows.append({
                "Resource": row['Resource'],
                "Start_D": format_d_time(s_dt),
                "End_D": format_d_time(e_dt),
                "Label": row['Label'],
                "Color": row['Color']
            })
        new_df = pd.DataFrame(processed_rows)
        
        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        st.download_button("📥 엑셀 다운로드", to_excel(new_df), 'schedule_final_v2.xlsx')
    except Exception as e:
        st.error(f"오류: {e}")