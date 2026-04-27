import asyncio
import json
import base64
import cv2
from channels.generic.websocket import AsyncWebsocketConsumer
from services.vision_service import VisionService


class VideoStreamConsumer(AsyncWebsocketConsumer):
    """Streams camera frames as base64 JPEG over WebSocket at ~15fps."""

    async def connect(self):
        await self.accept()
        self._streaming = True
        asyncio.create_task(self._stream_loop())

    async def disconnect(self, close_code):
        self._streaming = False

    async def _stream_loop(self):
        vision = VisionService()

        # Import here to avoid Django setup issues
        from core.models import SystemSettings

        try:
            settings = await asyncio.to_thread(SystemSettings.get_settings)
            await asyncio.to_thread(
                vision.open_camera,
                index=settings.camera_index,
                width=settings.camera_width,
                height=settings.camera_height,
                fps=settings.camera_fps,
            )
            camera_matrix = settings.get_camera_matrix()
            dist_coeffs = settings.get_dist_coeffs()
            tag_size_mm = settings.tag_size_mm
            aruco_dict_type = settings.aruco_dict_type
        except Exception as e:
            await self.send(text_data=json.dumps({
                'type': 'error', 'message': str(e)
            }))
            return

        while self._streaming:
            try:
                frame = await asyncio.to_thread(vision.capture_frame)
                display = await asyncio.to_thread(
                    vision.draw_aruco_overlay,
                    frame, camera_matrix, dist_coeffs, tag_size_mm,
                    aruco_dict_type
                )

                _, buffer = cv2.imencode('.jpg', display,
                                          [cv2.IMWRITE_JPEG_QUALITY, 65])
                b64 = base64.b64encode(buffer).decode('utf-8')

                await self.send(text_data=json.dumps({
                    'type': 'frame',
                    'image': b64,
                }))

                await asyncio.sleep(1 / 15)

            except Exception as e:
                await self.send(text_data=json.dumps({
                    'type': 'error', 'message': str(e)
                }))
                await asyncio.sleep(1)

    async def receive(self, text_data):
        data = json.loads(text_data)
        if data.get('command') == 'stop':
            self._streaming = False


class RobotStatusConsumer(AsyncWebsocketConsumer):
    """Periodically sends robot status over WebSocket."""

    async def connect(self):
        await self.accept()
        self._active = True
        asyncio.create_task(self._status_loop())

    async def disconnect(self, close_code):
        self._active = False

    async def _status_loop(self):
        from services.robot_service import RobotService

        while self._active:
            try:
                robot = RobotService()
                if robot.is_connected:
                    try:
                        info = await asyncio.to_thread(robot.get_robot_info)
                        pos = await asyncio.to_thread(robot.get_current_cart_pos)
                        status = {
                            'type': 'status',
                            'connected': True,
                            'info': info,
                            'position': pos,
                        }
                    except Exception as e:
                        # Connection flag is set but EKI query failed —
                        # still report connected, just without live data
                        status = {
                            'type': 'status',
                            'connected': True,
                            'error': str(e),
                        }
                else:
                    status = {'type': 'status', 'connected': False}

                await self.send(text_data=json.dumps(status, default=str))
            except Exception:
                await self.send(text_data=json.dumps({
                    'type': 'status', 'connected': False
                }))

            await asyncio.sleep(2)
