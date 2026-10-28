"""Testable control loop: retry without resetting the environment."""
import time

def execute(backend,raw_instruction,canonical_instruction,*,steps_per_attempt,max_attempts,
            instruction_mode='canonical',on_event=lambda event:None,on_step=lambda *args:None,
            before_action=lambda:True,on_retry=lambda attempt:True):
    if steps_per_attempt<1 or max_attempts<1:raise ValueError('Positive budgets required')
    if instruction_mode not in ['raw','canonical']:raise ValueError('Invalid instruction mode')
    events=[];total=0;started=time.monotonic()
    def emit(kind,**fields):
        event={'event':kind,'step':total,**fields};events.append(event);on_event(event)
    obs=backend.reset_environment() # Exactly one reset for this complete run.
    on_step(obs,0,0,'INITIAL')
    emit('environment_reset',count=1)
    for attempt in range(1,max_attempts+1):
        # Recovery changes the instruction to canonical and flushes queued actions.
        instruction=raw_instruction if attempt==1 and instruction_mode=='raw' else canonical_instruction
        backend.reset_policy()
        emit('attempt_begin',attempt=attempt,instruction=instruction,environment_reset=False)
        for local_step in range(steps_per_attempt):
            if not before_action():
                emit('cancelled',attempt=attempt)
                return {'success':False,'reason':'cancelled','attempts':attempt,'steps':total,
                        'wall_seconds':time.monotonic()-started,'events':events}
            action=backend.predict(obs,instruction)
            if not before_action():
                emit('cancelled',attempt=attempt)
                return {'success':False,'reason':'cancelled','attempts':attempt,'steps':total,
                        'wall_seconds':time.monotonic()-started,'events':events}
            obs,success,terminated,info=backend.step(action)
            total+=1
            on_step(obs,total,attempt,'SUCCESS' if success else 'EXECUTING')
            if success:
                emit('success',attempt=attempt,local_step=local_step+1)
                return {'success':True,'reason':'environment_goal_satisfied','attempts':attempt,
                        'steps':total,'wall_seconds':time.monotonic()-started,'events':events}
            if terminated:
                emit('environment_terminated',attempt=attempt)
                return {'success':False,'reason':'environment_terminated','attempts':attempt,
                        'steps':total,'wall_seconds':time.monotonic()-started,'events':events}
        emit('attempt_budget_exhausted',attempt=attempt,interpretation='goal_not_reached_within_budget')
        if attempt<max_attempts:
            if not on_retry(attempt):
                emit('retry_declined',attempt=attempt)
                return {'success':False,'reason':'retry_declined','attempts':attempt,'steps':total,
                        'wall_seconds':time.monotonic()-started,'events':events}
            emit('retry_current_state',next_attempt=attempt+1)
    return {'success':False,'reason':'all_budgets_exhausted','attempts':max_attempts,'steps':total,
            'wall_seconds':time.monotonic()-started,'events':events}
