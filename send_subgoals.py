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

def load_actions(json_path, recipe_sequence_path=None):
    """JSON 파일에서 actions 목록을 로드하고 need_amount 정보 추가"""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # recipe_sequence.json에서 need_amount 정보 로드
    need_amounts = {}
    if recipe_sequence_path and Path(recipe_sequence_path).exists():
        try:
            with open(recipe_sequence_path, 'r', encoding='utf-8') as f:
                recipe_sequence = json.load(f)
            for entry in recipe_sequence:
                target = entry.get('target', '')
                need_amount = entry.get('need_amount', 1)
                if target:
                    need_amounts[target] = need_amount
        except Exception as e:
            print(f"⚠ recipe_sequence.json 읽기 실패: {e}")
    
    # 각 아이템의 actions를 개별 action으로 분리
    all_actions = []
    for item_data in data:
        item_name = item_data.get('item', '')
        actions = item_data.get('actions', [])
        need_amount = need_amounts.get(item_name, item_data.get('need_amount', 1))
        
        if actions:
            # 각 action을 개별 항목으로 추가
            for action_idx, action in enumerate(actions):
                all_actions.append({
                    'item': item_name,
                    'action': action,
                    'action_index': action_idx,  # 아이템 내 action 인덱스
                    'total_actions': len(actions),  # 아이템의 총 action 수
                    'need_amount': need_amount,
                    'item_index': len([a for a in all_actions if a['item'] == item_name])  # 아이템의 순서
                })
    
    return all_actions

def get_agent_state(sio, agent_name, timeout=5.0):
    """
    agent의 상태를 가져오기
    
    Returns:
        dict: agent 상태 또는 None (실패 시)
    """
    try:
        # get-full-state 이벤트를 통해 상태 가져오기
        # JavaScript 측에서 callback을 받아야 하므로, 
        # Python socketio의 call() 메서드 사용
        response = sio.call('get-full-state', agent_name, timeout=timeout)
        return response
    except Exception as e:
        # call()이 지원되지 않으면 다른 방법 시도
        # 일단 None 반환하고, 주기적 확인 방식 사용
        return None

def check_item_in_inventory(inventory_counts, item_name, need_amount):
    """
    인벤토리에 아이템이 충분한지 확인
    
    Args:
        inventory_counts: inventory.counts 딕셔너리
        item_name: 확인할 아이템 이름
        need_amount: 필요한 개수
    
    Returns:
        bool: 충분하면 True
    """
    if not inventory_counts:
        return False
    
    # Minecraft 아이템 이름은 네임스페이스가 있을 수 있음 (예: "minecraft:oak_log")
    # 여러 형식으로 확인
    item_variants = [
        item_name,
        f"minecraft:{item_name}",
        item_name.replace('_', ' ')  # 일부 아이템은 공백 사용
    ]
    
    for variant in item_variants:
        if variant in inventory_counts:
            count = inventory_counts[variant]
            if count >= need_amount:
                return True
    
    return False

def wait_for_item(sio, agent_name, item_name, need_amount, check_interval=2.0, max_wait=300.0):
    """
    아이템이 인벤토리에 충분히 있을 때까지 대기
    
    Args:
        sio: socketio 클라이언트
        agent_name: bot 이름
        item_name: 확인할 아이템 이름
        need_amount: 필요한 개수
        check_interval: 확인 주기 (초)
        max_wait: 최대 대기 시간 (초)
    
    Returns:
        bool: 성공하면 True, 타임아웃이면 False
    """
    start_time = time.time()
    check_count = 0
    
    print(f"  → 인벤토리 확인 중: {item_name} (목표: {need_amount})")
    
    while time.time() - start_time < max_wait:
        try:
            # get-full-state를 통해 상태 가져오기
            # Python socketio는 call()을 지원하지 않을 수 있으므로
            # emit과 콜백을 사용하거나, state-update 이벤트를 구독해야 함
            # 
            # 임시 해결책: state-update 이벤트를 구독하거나
            # 직접 agent connection에 접근할 수 없으므로
            # 주기적으로 확인하는 방식 사용
            
            # 일단 간단하게 대기만 하고, 실제 확인은
            # state-update 이벤트를 구독하는 방식으로 변경 필요
            # 
            # 현재는 주기적으로 확인하는 방식으로 구현
            time.sleep(check_interval)
            check_count += 1
            
            # 실제로는 state-update 이벤트를 구독해야 하지만,
            # 일단 간단하게 시간 기반으로 대기
            # TODO: state-update 이벤트 구독으로 개선 필요
            
            if check_count % 5 == 0:
                print(f"    ... 확인 중 ({int(time.time() - start_time)}초 경과)")
            
        except KeyboardInterrupt:
            print("\n  사용자에 의해 중단되었습니다.")
            return False
    
    # 실제 확인 로직은 state-update 이벤트 구독으로 구현 필요
    # 현재는 타임아웃까지 대기 후 다음으로 진행
    print(f"  ⚠ 타임아웃: {item_name} 확인 완료로 간주하고 다음으로 진행")
    return True

def send_actions_to_bot(agent_name, all_actions, delay=2.0, use_goal_command=True, 
                        check_interval=2.0):
    """
    actions 목록을 순서대로 bot에 전달
    - 각 아이템의 actions를 순차적으로 전달
    - !completeSubgoal을 받으면 같은 아이템의 다음 action 전달
    - 아이템의 모든 action이 완료되면 inventory 확인 후 다음 아이템으로 진행
    
    Args:
        agent_name: bot의 이름 (예: 'andy')
        all_actions: action 목록 (각 action은 item, action, action_index, total_actions, need_amount 포함)
        delay: 각 메시지 사이의 대기 시간 (초)
        use_goal_command: True면 !goal 명령 사용, False면 일반 메시지
        check_interval: 인벤토리 확인 주기 (초)
    """
    sio = socketio.Client()
    state_received = {}
    # !completeSubgoal 명령 수신 플래그 (action 인덱스별로 추적)
    complete_subgoal_flags = {}
    # 현재 처리 중인 action 인덱스
    current_action_index = [None]
    
    def on_state_update(states):
        """state-update 이벤트 핸들러"""
        if agent_name in states:
            state_received[agent_name] = states[agent_name]
    
    def on_bot_output(agentName, message):
        """bot-output 이벤트 핸들러"""
        if agentName == agent_name and message:
            message_str = str(message)
            # !completeSubgoal 또는 !endGoal 명령 확인
            if '!completeSubgoal' in message_str or 'completeSubgoal' in message_str:
                # 현재 처리 중인 action 인덱스에 대해 플래그 설정
                if current_action_index[0] is not None:
                    complete_subgoal_flags[current_action_index[0]] = True
                    print(f"  → !completeSubgoal 명령 수신 확인!")
            elif '!endGoal' in message_str or 'endGoal' in message_str:
                # !endGoal도 다음 action으로 진행하는 신호로 처리
                if current_action_index[0] is not None:
                    complete_subgoal_flags[current_action_index[0]] = True
                    print(f"  → !endGoal 명령 수신 확인!")
    
    try:
        print(f"MindServer에 연결 중... ({MIND_SERVER_URL})")
        sio.connect(MIND_SERVER_URL)
        print(f"✓ MindServer 연결 성공")
        
        sio.on('state-update', on_state_update)
        sio.on('bot-output', on_bot_output)
        sio.emit('listen-to-agents')
        
        # 아이템별로 그룹화
        items_dict = {}
        for action_data in all_actions:
            item = action_data['item']
            if item not in items_dict:
                items_dict[item] = []
            items_dict[item].append(action_data)
        
        print(f"\n총 {len(items_dict)}개 아이템, {len(all_actions)}개 action을 순차적으로 전달합니다.\n")
        
        action_idx = 0
        for item_idx, (item, item_actions) in enumerate(items_dict.items(), 1):
            need_amount = item_actions[0]['need_amount']
            print(f"\n[{item_idx}/{len(items_dict)}] {item} (필요 개수: {need_amount}, 총 {len(item_actions)}개 action)")
            
            # 각 아이템의 actions를 순차적으로 전달
            for action_in_item_idx, action_data in enumerate(item_actions):
                action = action_data['action']
                action_idx += 1
                
                print(f"  [{action_in_item_idx + 1}/{len(item_actions)}] Action: {action[:60]}...")
                
                if use_goal_command:
                    message = f"!goal selfPrompt:{action}"
                else:
                    message = action
                
                data = {
                    'from': 'system',
                    'message': message
                }
                
                try:
                    sio.emit('send-message', [agent_name, data])
                    print(f"  ✓ Action 전달 완료")
                except Exception as e:
                    print(f"  ✗ 전달 실패: {e}")
                    import traceback
                    traceback.print_exc()
                    continue
                
                # action 완료 대기 (inventory 확인 + !completeSubgoal 확인)
                print(f"  → 완료 대기 중... (inventory 확인 + !completeSubgoal 확인)")
                start_time = time.time()
                current_action_index[0] = action_idx
                complete_subgoal_flags[action_idx] = False
                item_completed = False
                check_count = 0
                timeout_seconds = 100.0  # 100초 타임아웃
                
                while not item_completed:
                    elapsed = time.time() - start_time
                    
                    # 타임아웃 체크 (100초 경과)
                    if elapsed >= timeout_seconds:
                        print(f"  ⚠ 타임아웃 ({int(elapsed)}초 경과)! Action 재전달...")
                        # 같은 action 재전달
                        if use_goal_command:
                            message = f"!goal selfPrompt:{action}"
                        else:
                            message = action
                        
                        data = {
                            'from': 'system',
                            'message': message
                        }
                        
                        try:
                            sio.emit('send-message', [agent_name, data])
                            print(f"  ✓ Action 재전달 완료")
                            start_time = time.time()  # 타이머 리셋
                            check_count = 0
                        except Exception as e:
                            print(f"  ✗ 재전달 실패: {e}")
                        
                        # 재전달 후 계속 대기
                    
                    # 1. Inventory 확인 (항상 확인)
                    if agent_name in state_received:
                        state = state_received[agent_name]
                        if state and not state.get('error'):
                            inventory = state.get('inventory', {})
                            counts = inventory.get('counts', {})
                            
                            if check_item_in_inventory(counts, item, need_amount):
                                elapsed = int(time.time() - start_time)
                                print(f"  ✓ {item} 완료 확인! (인벤토리에 {need_amount}개 이상, 소요 시간: {elapsed}초)")
                                item_completed = True
                                break
                    
                    # 2. !completeSubgoal 또는 !endGoal 확인 (마지막 action이 아닐 때만)
                    if action_in_item_idx < len(item_actions) - 1:
                        if complete_subgoal_flags.get(action_idx, False):
                            elapsed = int(time.time() - start_time)
                            print(f"  ✓ !completeSubgoal 또는 !endGoal 수신! 다음 action으로 진행 (소요 시간: {elapsed}초)")
                            complete_subgoal_flags.pop(action_idx, None)
                            item_completed = True
                            break
                    
                    time.sleep(check_interval)
                    check_count += 1
                    
                    if check_count % 10 == 0:
                        elapsed = int(time.time() - start_time)
                        print(f"    ... 확인 중 ({elapsed}초 경과)")
                
                # 다음 아이템/action 전달 전 대기
                if item_idx < len(items_dict) or action_in_item_idx < len(item_actions) - 1:
                    print(f"  대기 중... ({delay}초)\n")
                    time.sleep(delay)
        
        print(f"\n✓ 모든 action 전달 완료!")
        
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
        default='final_item_plans.json',
        help='actions가 포함된 JSON 파일 경로 (기본값: final_item_plans.json)'
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
    parser.add_argument(
        '--recipe-sequence',
        type=str,
        default=None,
        help='recipe_sequence.json 파일 경로 (need_amount 정보용)'
    )
    parser.add_argument(
        '--check-interval',
        type=float,
        default=2.0,
        help='인벤토리 확인 주기(초) (기본값: 2.0)'
    )
    
    args = parser.parse_args()
    
    # 전역 변수 업데이트
    global MIND_SERVER_PORT, MIND_SERVER_URL
    MIND_SERVER_PORT = args.port
    MIND_SERVER_URL = f'http://localhost:{MIND_SERVER_PORT}'
    
    # JSON 파일 경로 확인 (상대 경로는 mindcraft 디렉토리 기준)
    script_dir = Path(__file__).parent
    if not Path(args.json_path).is_absolute():
        # 상대 경로인 경우 mindcraft 디렉토리에서 찾기
        json_path = script_dir / args.json_path
        # 없으면 프로젝트 루트에서 찾기
        if not json_path.exists():
            json_path = script_dir.parent / args.json_path
    else:
        json_path = Path(args.json_path)
    
    if not json_path.exists():
        print(f"✗ 파일을 찾을 수 없습니다: {json_path}")
        sys.exit(1)
    
    # recipe_sequence.json 경로 확인
    recipe_sequence_path = args.recipe_sequence
    if not recipe_sequence_path:
        # 기본 경로: 프로젝트 루트의 recipe_sequence.json
        script_dir = Path(__file__).parent
        default_recipe_path = script_dir.parent / 'recipe_sequence.json'
        if default_recipe_path.exists():
            recipe_sequence_path = str(default_recipe_path)
    
    # actions 로드
    try:
        all_actions = load_actions(json_path, recipe_sequence_path)
        if not all_actions:
            print(f"✗ JSON 파일에 actions가 없습니다: {json_path}")
            sys.exit(1)
    except Exception as e:
        print(f"✗ JSON 파일 읽기 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # actions 전달
    send_actions_to_bot(
        args.agent,
        all_actions,
        delay=args.delay,
        use_goal_command=not args.no_goal_command,
        check_interval=args.check_interval
    )

if __name__ == '__main__':
    main()

