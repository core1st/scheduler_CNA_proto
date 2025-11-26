import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta, time
import streamlit.components.v1 as components
from io import BytesIO
import re

# --- 1. 페이지 설정 및 초기화 ---
st.set_page_config(layout="wide", page_title="B787-9 Rotation (Final Editor)")
st.title("✈️ B787-9 Rotation Scheduler (Direct Table Editor)")

BASE_DATE = datetime(2024, 1, 1)

# 세션 상태 초기화: 데이터프레임을 세션에 저장하여 편집 상태 유지
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
if 'custom_resources' not in st.session_state:
    st.session_state.custom_resources = []

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
    diff = dt - BASE_DATE
    day_num = (diff.days % 7) + 1
    return f"D{day_num} {dt.hour:02d}{dt.minute:02d}"

# Natural Sort (숫자 인식 정렬)
def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

# --- 3. 데이터 로드 및 전처리 ---
def load_data(uploaded_file):
    if uploaded_file:
        df = pd.read_excel(uploaded_file)
    else:
        # 샘플 데이터
        df = pd.DataFrame([
            {"Resource": "#1", "Start_D": "D1 1320", "End_D": "D2 1620", "Label": "LAX", "Color": "#FFB6C1"},
            {"Resource": "#2", "Start_D": "D1 2155", "End_D": "D2 0540", "Label": "EWR", "Color": "#ADD8E6"},
        ])
    
    # 필수 컬럼 보정
    if 'Color' not in df.columns: df['Color'] = '#ADD8E6'
    if 'Resource' not in df.columns: df['Resource'] = 'Unassigned'
    if 'Label' not in df.columns: df['Label'] = 'Flight'
    
    return df

# --- 4. 사이드바: 파일 로드 & 기재 관리 ---
st.sidebar.header("1. 데이터 관리")
uploaded_file = st.sidebar.file_uploader("엑셀 업로드", type=["xlsx"])

# 파일이 업로드되거나 초기 상태일 때 데이터 로드 (한 번만)
if st.session_state.schedule_df is None or uploaded_file is not None:
    # 업로드 파일이 바뀌면 리셋
    if uploaded_file:
        st.session_state.schedule_df = load_data(uploaded_file)
    elif st.session_state.schedule_df is None:
        st.session_state.schedule_df = load_data(None)

st.sidebar.markdown("---")
st.sidebar.header("2. 기재(Row) 추가")
with st.sidebar.expander("➕ 새 기재 이름 등록"):
    new_row_name = st.text_input("기재 이름 (예: #10)")
    if st.button("기재 등록"):
        if new_row_name and new_row_name not in st.session_state.custom_resources:
            st.session_state.custom_resources.append(new_row_name)
            st.rerun()

# 리소스 목록 취합
base_resources = [f"#{i}" for i in range(1, 9)]
existing = st.session_state.schedule_df['Resource'].unique().tolist()
custom = st.session_state.custom_resources
all_resources = sorted(list(set(base_resources + existing + custom)), key=natural_sort_key)


# --- 5. [핵심] 데이터 테이블 에디터 (st.data_editor) ---
st.subheader("📊 스케줄 데이터 편집 (직접 수정/추가/삭제)")
st.info("💡 아래 표에서 직접 내용을 수정하거나, 맨 아래행을 클릭해 추가, 왼쪽 체크박스로 삭제하세요. (Start_D/End_D 형식: D1 1300)")

# 에디터 설정
edited_df = st.data_editor(
    st.session_state.schedule_df,
    num_rows="dynamic", # 행 추가/삭제 허용
    column_config={
        "Resource": st.column_config.SelectboxColumn(
            "기재",
            help="투입될 항공기 기재",
            width="medium",
            options=all_resources,
            required=True,
        ),
        "Start_D": st.column_config.TextColumn("출발 (예: D1 1320)", required=True),
        "End_D": st.column_config.TextColumn("도착 (예: D2 0540)", required=True),
        "Label": st.column_config.TextColumn("목적지/편명", required=True),
        "Color": st.column_config.ColorPickerColumn("색상"),
        # 내부 계산용 컬럼 숨기기
        "Start": None, "End": None 
    },
    use_container_width=True,
    key="editor", # 키를 지정하여 변경사항 추적
    hide_index=True
)

# 데이터가 수정되었으면 세션에 업데이트
if not edited_df.equals(st.session_state.schedule_df):
    st.session_state.schedule_df = edited_df
    # 날짜 계산 다시 수행 (Start_D -> Start datetime)
    st.session_state.schedule_df['Start'] = st.session_state.schedule_df['Start_D'].apply(parse_d_time)
    st.session_state.schedule_df['End'] = st.session_state.schedule_df['End_D'].apply(parse_d_time)
    st.rerun() # 차트 갱신을 위해 새로고침

# 현재 데이터프레임 확정
final_df = st.session_state.schedule_df.copy()
# Start/End 컬럼이 없을 경우를 대비해 한번 더 계산
if 'Start' not in final_df.columns:
    final_df['Start'] = final_df['Start_D'].apply(parse_d_time)
    final_df['End'] = final_df['End_D'].apply(parse_d_time)


# --- 6. JSON 변환 (차트용) ---
# 그룹(Row) 정의 (순서 고정)
groups = [{"id": res, "content": f"<b>{res}</b>", "order": i} for i, res in enumerate(all_resources)]

items = []
for i, row in final_df.iterrows():
    # 유효하지 않은 날짜 데이터 제외
    if pd.isna(row['Start']) or pd.isna(row['End']): continue
    
    c_val = row['Color'] if not pd.isna(row['Color']) else '#ADD8E6'
    items.append({
        "id": i, 
        "group": row['Resource'], 
        "content": str(row['Label']),
        "start": row['Start'].isoformat(), 
        "end": row['End'].isoformat(),
        "style": f"background-color: {c_val}; border-color: black;"
    })

# --- 7. HTML/JS (Vis.js Timeline) ---
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
<button class="btn-copy" onclick="exportData()">💾 차트 위치 저장 (복사)</button>
<span id="msg" style="color: green; margin-left: 10px;"></span>
<script>
  try {{
      var groups = new vis.DataSet({json.dumps(groups)});
      var items = new vis.DataSet({json.dumps(items)});
      var container = document.getElementById('visualization');
      
      var options = {{
        groupOrder: 'order', // 순번대로 정렬
        editable: true, stack: false, margin: {{ item: 5, axis: 5 }}, orientation: 'top',
        min: '2024-01-01 00:00:00', max: '2024-01-08 00:00:00',
        start: '2024-01-01 00:00:00', end: '2024-01-08 00:00:00',
        zoomMin: 1000 * 60 * 60 * 6, zoomMax: 1000 * 60 * 60 * 24 * 7,
        format: {{
          minorLabels: function(date, scale, step) {{ return new Date(date).getHours() + 'h'; }},
          majorLabels: function(date, scale, step) {{ return 'D' + new Date(date).getDate(); }}
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

st.markdown("---")
st.subheader("📊 인터랙티브 스케줄러")
components.html(html_code, height=650)


# --- 8. 저장 ---
st.markdown("---")
st.subheader("📥 결과 저장")
json_input = st.text_area("위의 '차트 위치 저장' 버튼으로 복사한 데이터를 여기에 붙여넣으세요 (Ctrl+V)", height=100)

if json_input:
    try:
        new_data = json.loads(json_input)
        processed_rows = []
        for row in new_data:
            s_dt = pd.to_datetime(row['Start_ISO'])
            e_dt = pd.to_datetime(row['End_ISO'])
            processed_rows.append({
                "Resource": row['Resource'],
                "Start_D": format_d_time(s_dt), "End_D": format_d_time(e_dt),
                "Label": row['Label'], "Color": row['Color']
            })
        
        export_df = pd.DataFrame(processed_rows)
        # Resource 정렬 (Natural Sort)
        export_df['Resource'] = pd.Categorical(export_df['Resource'], categories=all_resources, ordered=True)
        export_df = export_df.sort_values('Resource')

        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        st.download_button("📥 엑셀 파일 다운로드", to_excel(export_df), 'schedule_final.xlsx')
    except Exception as e:
        st.error(f"오류: {e}")