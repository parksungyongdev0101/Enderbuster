#!/usr/bin/env python3
"""
JSON 파일의 subgoal을 순서대로 mindcraft bot에 전달하는 스크립트
"""

import json
import time
import sys
from pathlib import Path

# python-socketio 패키지 import 확인
try:
    import socketio
    # Client 클래스가 있는지 확인
    if not hasattr(socketio, 'Client'):
        raise ImportError("python-socketio 패키지가 올바르게 설치되지 않았습니다. 'pip install python-socketio'를 실행하세요.")
except ImportError as e:
    print(f"✗ socketio 모듈을 import할 수 없습니다: {e}")
    print("  다음 명령으로 설치하세요: pip install python-socketio")
    sys.exit(1)

# MindServer 연결 설정
MIND_SERVER_PORT = 8080
MIND_SERVER_URL = f'http://localhost:{MIND_SERVER_PORT}'

def load_subgoals(json_path):
    """JSON 파일에서 subgoal 목록을 로드"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    subgoals = []
    for item in data:
        if 'subgoal' in item and item['subgoal']:
            subgoals.append({
                'item': item.get('item', ''),
                'subgoal': item['subgoal'],
                'index': len(subgoals) + 1
            })
    
    return subgoals

def send_subgoals_to_bot(agent_name, subgoals, delay=2.0, use_goal_command=True):
    """
    subgoal 목록을 순서대로 bot에 전달
    
    Args:
        agent_name: bot의 이름 (예: 'andy')
        subgoals: subgoal 목록
        delay: 각 메시지 사이의 대기 시간 (초)
        use_goal_command: True면 !goal 명령 사용, False면 일반 메시지
    """
    sio = socketio.Client()
    
    try:
        print(f"MindServer에 연결 중... ({MIND_SERVER_URL})")
        sio.connect(MIND_SERVER_URL)
        print(f"✓ MindServer 연결 성공")
        
        print(f"\n총 {len(subgoals)}개의 subgoal을 전달합니다.\n")
        
        for i, subgoal_data in enumerate(subgoals, 1):
            item = subgoal_data['item']
            subgoal = subgoal_data['subgoal']
            
            print(f"[{i}/{len(subgoals)}] {item}")
            print(f"  Subgoal: {subgoal[:80]}...")
            
            if use_goal_command:
                # !goal 명령 사용
                message = f"!goal selfPrompt:{subgoal}"
            else:
                # 일반 메시지로 전달
                message = subgoal
            
            # MindServer의 send-message 이벤트로 전달
            # Python socketio는 여러 인자를 개별적으로 전달할 수 없으므로
            # [agentName, data] 배열로 전달합니다.
            # JavaScript 측 코드가 이를 처리하도록 수정되었습니다.
            data = {
                'from': 'system',
                'message': message
            }
            
            try:
                # Python socketio는 여러 인자를 리스트로 전달하면
                # JavaScript에서 첫 번째 인자로 배열을 받게 됩니다.
                # JavaScript 측 코드가 이를 처리하도록 수정되었습니다.
                sio.emit('send-message', [agent_name, data])
                print(f"  ✓ 전달 완료")
            except Exception as e:
                print(f"  ✗ 전달 실패: {e}")
                import traceback
                traceback.print_exc()
            
            # 마지막 항목이 아니면 대기
            if i < len(subgoals):
                print(f"  대기 중... ({delay}초)\n")
                time.sleep(delay)
        
        print(f"\n✓ 모든 subgoal 전달 완료!")
        
    except socketio.exceptions.ConnectionError as e:
        print(f"✗ MindServer 연결 실패: {e}")
        print(f"  MindServer가 실행 중인지 확인하세요. (포트 {MIND_SERVER_PORT})")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n사용자에 의해 중단되었습니다.")
    except Exception as e:
        print(f"✗ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if sio.connected:
            sio.disconnect()
            print("MindServer 연결 종료")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description='JSON 파일의 subgoal을 순서대로 mindcraft bot에 전달'
    )
    parser.add_argument(
        'json_path',
        type=str,
        nargs='?',
        default='item_plans.json',
        help='subgoal이 포함된 JSON 파일 경로 (기본값: item_plans.json)'
    )
    parser.add_argument(
        '--agent',
        type=str,
        default='andy',
        help='bot 이름 (기본값: andy)'
    )
    parser.add_argument(
        '--delay',
        type=float,
        default=2.0,
        help='각 메시지 사이의 대기 시간(초) (기본값: 2.0)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=8080,
        help=f'MindServer 포트 (기본값: 55916)'
    )
    parser.add_argument(
        '--no-goal-command',
        action='store_true',
        help='!goal 명령 대신 일반 메시지로 전달'
    )
    
    args = parser.parse_args()
    
    # 전역 변수 업데이트
    global MIND_SERVER_PORT, MIND_SERVER_URL
    MIND_SERVER_PORT = args.port
    MIND_SERVER_URL = f'http://localhost:{MIND_SERVER_PORT}'
    
    # JSON 파일 경로 확인 (상대 경로는 mindcraft 디렉토리 기준)
    script_dir = Path(__file__).parent
    json_path = script_dir / args.json_path if not Path(args.json_path).is_absolute() else Path(args.json_path)
    
    if not json_path.exists():
        print(f"✗ 파일을 찾을 수 없습니다: {json_path}")
        sys.exit(1)
    
    # subgoal 로드
    try:
        subgoals = load_subgoals(json_path)
        if not subgoals:
            print(f"✗ JSON 파일에 subgoal이 없습니다: {json_path}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ JSON 파일 읽기 실패: {e}")
        sys.exit(1)
    
    # subgoal 전달
    send_subgoals_to_bot(
        args.agent,
        subgoals,
        delay=args.delay,
        use_goal_command=not args.no_goal_command
    )

if __name__ == '__main__':
    main()

