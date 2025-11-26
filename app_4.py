import streamlit as st
import pandas as pd
import json
from datetime import datetime, timedelta, time
import streamlit.components.v1 as components
from io import BytesIO
import re

# --- 1. 페이지 설정 및 초기화 ---
st.set_page_config(layout="wide", page_title="A/C Rotation (Unified)")
st.title("✈️ A/C Rotation Scheduler")

BASE_DATE = datetime(2024, 1, 1)

# 세션 상태 초기화
if 'schedule_df' not in st.session_state:
    st.session_state.schedule_df = None
if 'custom_resources' not in st.session_state:
    st.session_state.custom_resources = []

# --- 2. 헬퍼 함수 ---
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

def natural_sort_key(s):
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', str(s))]

# --- 3. 데이터 로드 ---
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
    for col, default in [('Color', '#ADD8E6'), ('Resource', 'Unassigned'), ('Label', 'Flight')]:
        if col not in df.columns: df[col] = default
            
    # Start/End Datetime 계산
    if 'Start_D' in df.columns:
        df['Start'] = df['Start_D'].apply(parse_d_time)
        df['End'] = df['End_D'].apply(parse_d_time)
        
    return df

# --- 4. 사이드바: 기본 설정 ---
st.sidebar.header("1. 데이터 파일")
uploaded_file = st.sidebar.file_uploader("엑셀 업로드", type=["xlsx"])

# 초기 데이터 로드
if st.session_state.schedule_df is None or uploaded_file is not None:
    if uploaded_file:
        st.session_state.schedule_df = load_data(uploaded_file)
    elif st.session_state.schedule_df is None:
        st.session_state.schedule_df = load_data(None)

# 기재 목록 관리
st.sidebar.markdown("---")
st.sidebar.header("2. 기재(Row) 관리")
with st.sidebar.expander("➕ 새 기재 이름 등록"):
    new_row_name = st.text_input("기재 이름 (예: #10)")
    if st.button("기재 등록"):
        if new_row_name and new_row_name not in st.session_state.custom_resources:
            st.session_state.custom_resources.append(new_row_name)
            st.rerun()

# 리소스 목록 통합
base_resources = [f"#{i}" for i in range(1, 9)]
existing = st.session_state.schedule_df['Resource'].unique().tolist()
custom = st.session_state.custom_resources
all_resources = sorted(list(set(base_resources + existing + custom)), key=natural_sort_key)


# --- 5. 사이드바 스케줄 추가 폼 ---
st.sidebar.markdown("---")
st.sidebar.header("3. 스케줄 추가 (폼 입력)")

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
        # 1. 시간 계산
        day_off = int(f_day[1:]) - 1
        s_dt = BASE_DATE + timedelta(days=day_off, hours=f_time.hour, minutes=f_time.minute)
        e_dt = s_dt + timedelta(hours=dur_h, minutes=dur_m)
        
        # 2. 새 데이터 행 생성
        new_row = pd.DataFrame([{
            "Resource": f_res,
            "Label": f_lbl,
            "Color": f_col,
            "Start_D": format_d_time(s_dt),
            "End_D": format_d_time(e_dt),
            "Start": s_dt,
            "End": e_dt
        }])
        
        # 3. 기존 데이터프레임에 병합 (concat)
        st.session_state.schedule_df = pd.concat([st.session_state.schedule_df, new_row], ignore_index=True)
        
        # 4. 새로고침 (즉시 반영)
        st.success("폼을 통해 추가되었습니다!")
        st.rerun()


# --- 6. 메인 화면: 데이터 에디터 ---
st.subheader("📊A/C 패턴표 작성용")
st.info("사이드바+테이블 직접 입력 가능")

# 데이터 에디터 출력
edited_df = st.data_editor(
    st.session_state.schedule_df,
    num_rows="dynamic",
    column_config={
        "Resource": st.column_config.SelectboxColumn("기재", options=all_resources, required=True),
        "Start_D": st.column_config.TextColumn("출발 (D1 1320)", required=True),
        "End_D": st.column_config.TextColumn("도착 (D2 0540)", required=True),
        "Label": st.column_config.TextColumn("목적지", required=True),
        # [수정됨] ColorPickerColumn -> TextColumn으로 변경 (구버전 호환성 해결)
        "Color": st.column_config.TextColumn("색상 (예: #FF0000)"),
        "Start": None, "End": None # 숨김
    },
    use_container_width=True,
    key="schedule_editor",
    hide_index=True
)

# 직접 수정 시 업데이트 로직
if not edited_df.equals(st.session_state.schedule_df):
    st.session_state.schedule_df = edited_df
    # 날짜 재계산 (직접 입력한 텍스트 -> Datetime 변환)
    st.session_state.schedule_df['Start'] = st.session_state.schedule_df['Start_D'].apply(parse_d_time)
    st.session_state.schedule_df['End'] = st.session_state.schedule_df['End_D'].apply(parse_d_time)
    st.rerun()

# --- 7. 시각화 데이터 준비 ---
final_df = st.session_state.schedule_df.copy()

groups = [{"id": res, "content": f"<b>{res}</b>", "order": i} for i, res in enumerate(all_resources)]
items = []

for i, row in final_df.iterrows():
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

# --- 8. Vis.js 타임라인 ---
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
    .vis-item {{ border-width: 1px; font-weight: bold; font-size: 12px; display: flex; align-items: center; justify-content: center; }}
    .btn-copy {{ margin-top: 10px; padding: 10px 20px; background-color: #ff4b4b; color: white; border: none; border-radius: 5px; cursor: pointer; }}
  </style>
</head>
<body>
<div id="visualization"></div>
<button class="btn-copy" onclick="exportData()">💾 차트 데이터 복사</button>
<span id="msg" style="color: green; margin-left: 10px;"></span>
<script>
  try {{
      var groups = new vis.DataSet({json.dumps(groups)});
      var items = new vis.DataSet({json.dumps(items)});
      var container = document.getElementById('visualization');
      
      var options = {{
        groupOrder: 'order',
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
            document.getElementById('msg').innerText = "복사 완료! 아래에 붙여넣으세요.";
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
st.subheader("📊 인터랙티브 차트")
components.html(html_code, height=650)

# --- 9. 저장 ---
st.markdown("---")
st.subheader("📥 엑셀 저장")
json_input = st.text_area("위의 '차트 데이터 복사' 버튼을 누른 후, 여기에 붙여넣기 (Ctrl+V)", height=100)

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
        export_df['Resource'] = pd.Categorical(export_df['Resource'], categories=all_resources, ordered=True)
        export_df = export_df.sort_values('Resource')

        def to_excel(df):
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)
            return output.getvalue()

        st.download_button("📥 엑셀 다운로드", to_excel(export_df), 'schedule_final.xlsx')
    except Exception as e:
        st.error(f"오류: {e}")