import traceback
try:
    import cv2
    import mediapipe as mp
    from mediapipe.tasks import python as mp_python
    from mediapipe.tasks.python import vision as mp_vision
    print('TASKS_AVAILABLE=True')
except Exception as e:
    print('TASKS_AVAILABLE=False')
    traceback.print_exc()
