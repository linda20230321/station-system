"""
铁路广播监测系统 - 后端主程序
功能：音频采集、实时推送、录音存储、历史回放API、区域设备管理
"""

from flask import Flask, render_template, send_file, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS

# 解决pyaudio导入问题 - 在云服务器上可能没有pyaudio
try:
    import pyaudio
    PYAVAILABLE = True
except ImportError:
    PYAVAILABLE = False
    print("警告: pyaudio未安装，将使用模拟模式")
    # 创建一个虚拟的pyaudio模块
    class MockPaInt16:
        pass
    
    class MockPyAudio:
        def __init__(self):
            pass
        def terminate(self):
            pass
        def open(self, **kwargs):
            return None
    
    pyaudio = type('pyaudio', (), {
        'paInt16': MockPaInt16(),
        'PyAudio': MockPyAudio
    })()

import wave
import threading
import time
import os
import sqlite3
import datetime
import json
import numpy as np
from pathlib import Path
from queue import Queue
import uuid
import logging
import random
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'railway-broadcast-monitor-2024'
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 3600  # 静态文件缓存
CORS(app)

# 使用 polling 模式而不是 websocket，更适合云服务器
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading', 
                    ping_timeout=60, ping_interval=25)


class DeviceStatus(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    ALERT = "alert"


@dataclass
class Device:
    """拾音器信息"""
    id: str
    name: str
    station: str
    area_level2: str
    area_level3: str
    area_level4: str
    status: DeviceStatus
    ip: str
    mac: str
    last_heartbeat: datetime.datetime = None


@dataclass
class AreaBinding:
    """区域绑定关系"""
    id: str
    level1: str
    level2: str
    level3: str
    level4: str
    device_ids: List[str]


# 添加缓存装饰器
def cached(timeout=5):
    def decorator(func):
        cache = {}
        @wraps(func)
        def wrapper(*args, **kwargs):
            key = str(args) + str(sorted(kwargs.items()))
            now = time.time()
            if key in cache and now - cache[key][0] < timeout:
                return cache[key][1]
            result = func(*args, **kwargs)
            cache[key] = (now, result)
            return result
        return wrapper
    return decorator


class AudioMonitorSystem:
    """音频监控系统核心类"""

    def __init__(self):
        # 加载配置
        self.load_config()

        # 音频参数
        self.CHUNK = self.config.get('chunk', 1024)
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = self.config.get('channels', 1)
        self.RATE = self.config.get('sample_rate', 16000)

        # 状态变量
        self.is_recording = False
        self.devices: Dict[str, Device] = {}
        self.area_bindings: Dict[str, AreaBinding] = {}

        # 初始化PyAudio
        self.p = None
        self.init_pyaudio()

        # 创建存储目录
        self.recording_dir = Path(self.config.get('recording_dir', 'recordings'))
        self.recording_dir.mkdir(exist_ok=True)

        # 初始化数据库
        self.init_database()

        # WebSocket连接管理
        self.clients = set()

        # 音量监测
        self.device_volumes: Dict[str, float] = {}

        # 缓存统计信息
        self._stats_cache = None
        self._stats_cache_time = 0
        self._bindings_cache = None
        self._bindings_cache_time = 0

        # 初始化数据（减少模拟数据量）
        self.init_area_hierarchy()
        self.init_mock_devices()
        self.init_mock_recordings_reduced()  # 使用减少的数据量
        self.init_area_bindings()

        # 启动告警监测线程（降低频率）
        self.start_alert_monitor()

        logger.info("铁路广播监测系统初始化完成")

    def load_config(self):
        """加载配置文件"""
        default_config = {
            'chunk': 1024,
            'sample_rate': 16000,
            'channels': 1,
            'recording_dir': 'recordings',
            'max_recordings': 10000,
            'volume_threshold_low': 20,
            'volume_threshold_high': 80,
            'heartbeat_interval': 30,
            'offline_timeout': 60
        }

        config_file = 'config.json'
        if os.path.exists(config_file):
            with open(config_file, 'r', encoding='utf-8') as f:
                self.config = json.load(f)
                for key, value in default_config.items():
                    if key not in self.config:
                        self.config[key] = value
        else:
            self.config = default_config
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)

    def init_pyaudio(self):
        """初始化PyAudio"""
        if not PYAVAILABLE:
            logger.warning("PyAudio不可用，将使用模拟模式")
            self.p = None
            return
            
        try:
            self.p = pyaudio.PyAudio()
            logger.info("PyAudio初始化成功")
        except Exception as e:
            logger.warning(f"PyAudio初始化失败: {e}，将使用模拟数据")
            self.p = None

    def init_database(self):
        """初始化数据库"""
        try:
            db_path = 'railway_broadcast.db'
            self.conn = sqlite3.connect(db_path, check_same_thread=False)
            self.cursor = self.conn.cursor()

            # 删除旧表重建
            self.cursor.execute('DROP TABLE IF EXISTS recordings')
            self.cursor.execute('DROP TABLE IF EXISTS devices')
            self.cursor.execute('DROP TABLE IF EXISTS area_bindings')

            # 创建拾音器表
            self.cursor.execute('''
                CREATE TABLE devices (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT NOT NULL,
                    station TEXT NOT NULL,
                    area_level2 TEXT NOT NULL,
                    area_level3 TEXT NOT NULL,
                    area_level4 TEXT NOT NULL,
                    status TEXT DEFAULT 'offline',
                    ip TEXT,
                    mac TEXT,
                    last_heartbeat TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 录音记录表
            self.cursor.execute('''
                CREATE TABLE recordings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    record_id TEXT UNIQUE NOT NULL,
                    device_id TEXT NOT NULL,
                    device_name TEXT NOT NULL,
                    area_level2 TEXT,
                    area_level3 TEXT,
                    area_level4 TEXT,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    start_time TIMESTAMP NOT NULL,
                    end_time TIMESTAMP,
                    duration REAL,
                    file_size INTEGER,
                    avg_volume REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (device_id) REFERENCES devices(device_id)
                )
            ''')

            # 区域绑定表
            self.cursor.execute('''
                CREATE TABLE area_bindings (
                    id TEXT PRIMARY KEY,
                    level1 TEXT NOT NULL,
                    level2 TEXT NOT NULL,
                    level3 TEXT NOT NULL,
                    level4 TEXT NOT NULL,
                    device_ids TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 创建索引
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_recordings_device ON recordings(device_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_recordings_time ON recordings(start_time DESC)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_devices_area ON devices(area_level2, area_level3, area_level4)')

            self.conn.commit()
            logger.info("数据库初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")
            raise

    def init_area_hierarchy(self):
        """初始化区域层级"""
        self.area_data = {
            "重庆东站": {
                "候车室": {
                    "A区检票口": ["A2、A3检票口", "A7、A8检票口", "A12、A13检票口"],
                    "B区检票口": ["B1检票口", "B5、B6检票口", "B14、B15检票口"],
                },
                "出站口": {
                    "北出站口": ["北出站大厅", "北出站通道"],
                    "南出站口": ["南出站大厅", "南出站通道"],
                    "东出站口": ["东出站大厅"]
                },
                "进站口": {
                    "北进站口": ["北进站大厅", "北安检区"],
                    "南进站口": ["南进站大厅", "南安检区"],
                    "西进站口": ["西进站大厅"]
                },
                "换乘大厅": {
                    "地铁换乘区": ["地铁换乘通道", "地铁换乘大厅"],
                    "公交换乘区": ["公交候车区", "公交上客区"]
                }
            }
        }
        logger.info(f"区域层级初始化完成")

    def init_mock_devices(self):
        """初始化模拟拾音器 - 每个区域绑定2-3个传感器"""
        device_counter = 1
        devices_config = [
            # 候车室区域 - A2、A3检票口区域绑定2个传感器
            ("候车室", "A区检票口", "A2、A3检票口", "候车室-A2检票口传感器"),
            ("候车室", "A区检票口", "A2、A3检票口", "候车室-A3检票口传感器"),
            # 候车室 - A7、A8检票口区域绑定2个传感器
            ("候车室", "A区检票口", "A7、A8检票口", "候车室-A7检票口传感器"),
            ("候车室", "A区检票口", "A7、A8检票口", "候车室-A8检票口传感器"),
            # 候车室 - A12、A13检票口区域绑定2个传感器
            ("候车室", "A区检票口", "A12、A13检票口", "候车室-A12检票口传感器"),
            ("候车室", "A区检票口", "A12、A13检票口", "候车室-A13检票口传感器"),
            # 候车室 - B1检票口区域绑定1个传感器
            ("候车室", "B区检票口", "B1检票口", "候车室-B1检票口传感器"),
            # 候车室 - B5、B6检票口区域绑定2个传感器
            ("候车室", "B区检票口", "B5、B6检票口", "候车室-B5检票口传感器"),
            ("候车室", "B区检票口", "B5、B6检票口", "候车室-B6检票口传感器"),
            # 候车室 - B14、B15检票口区域绑定2个传感器
            ("候车室", "B区检票口", "B14、B15检票口", "候车室-B14检票口传感器"),
            ("候车室", "B区检票口", "B14、B15检票口", "候车室-B15检票口传感器"),
            # 出站口 - 北出站大厅绑定2个传感器
            ("出站口", "北出站口", "北出站大厅", "北出站大厅-东侧传感器"),
            ("出站口", "北出站口", "北出站大厅", "北出站大厅-西侧传感器"),
            # 出站口 - 北出站通道绑定1个传感器
            ("出站口", "北出站口", "北出站通道", "北出站通道传感器"),
            # 出站口 - 南出站大厅绑定2个传感器
            ("出站口", "南出站口", "南出站大厅", "南出站大厅-东侧传感器"),
            ("出站口", "南出站口", "南出站大厅", "南出站大厅-西侧传感器"),
            # 出站口 - 东出站大厅绑定1个传感器
            ("出站口", "东出站口", "东出站大厅", "东出站大厅传感器"),
            # 进站口 - 北进站大厅绑定2个传感器
            ("进站口", "北进站口", "北进站大厅", "北进站大厅-1号通道传感器"),
            ("进站口", "北进站口", "北进站大厅", "北进站大厅-2号通道传感器"),
            # 进站口 - 北安检区绑定1个传感器
            ("进站口", "北进站口", "北安检区", "北安检区传感器"),
            # 进站口 - 南进站大厅绑定2个传感器
            ("进站口", "南进站口", "南进站大厅", "南进站大厅-1号通道传感器"),
            ("进站口", "南进站口", "南进站大厅", "南进站大厅-2号通道传感器"),
            # 进站口 - 西进站大厅绑定1个传感器
            ("进站口", "西进站口", "西进站大厅", "西进站大厅传感器"),
            # 换乘大厅 - 地铁换乘通道绑定2个传感器
            ("换乘大厅", "地铁换乘区", "地铁换乘通道", "地铁换乘通道-北侧传感器"),
            ("换乘大厅", "地铁换乘区", "地铁换乘通道", "地铁换乘通道-南侧传感器"),
            # 换乘大厅 - 地铁换乘大厅绑定2个传感器
            ("换乘大厅", "地铁换乘区", "地铁换乘大厅", "地铁换乘大厅-中央传感器"),
            ("换乘大厅", "地铁换乘区", "地铁换乘大厅", "地铁换乘大厅-出口传感器"),
        ]

        for level2, level3, level4, device_name in devices_config:
            device_id = f"MIC_{device_counter:03d}"

            # 随机状态（大部分在线）
            status_choice = [DeviceStatus.ONLINE] * 8 + [DeviceStatus.OFFLINE, DeviceStatus.ALERT]
            status = status_choice[device_counter % len(status_choice)]

            device = Device(
                id=device_id,
                name=device_name,
                station="重庆东站",
                area_level2=level2,
                area_level3=level3,
                area_level4=level4,
                status=status,
                ip=f"192.168.{device_counter // 256}.{device_counter % 256}",
                mac=f"00:15:5d:{device_counter:02x}:{(device_counter+1):02x}:{(device_counter+2):02x}",
                last_heartbeat=datetime.datetime.now()
            )

            self.devices[device_id] = device
            self.device_volumes[device_id] = 0  # 默认音量为0

            # 保存到数据库
            self.cursor.execute('''
                INSERT INTO devices 
                (device_id, device_name, station, area_level2, area_level3, area_level4, 
                 status, ip, mac, last_heartbeat)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (device_id, device.name, device.station, device.area_level2,
                  device.area_level3, device.area_level4, device.status.value,
                  device.ip, device.mac, device.last_heartbeat))

            device_counter += 1

        self.conn.commit()
        logger.info(f"初始化了 {len(self.devices)} 个拾音器")

    def init_mock_recordings_reduced(self):
        """初始化模拟录音数据 - 减少数据量以提高性能"""
        now = datetime.datetime.now()
        mock_recordings = []

        # 为每个拾音器生成录音数据（只生成最近7天，而不是30天）
        for device in self.devices.values():
            if device.status == DeviceStatus.OFFLINE:
                continue

            # 为每个传感器生成最近7天的整体录音（每天一段）
            for day_offset in range(7):
                # 每天生成一段整体录音
                start_hour = random.randint(6, 8)
                start_minute = random.randint(0, 59)
                start_second = random.randint(0, 59)

                start_time = now - datetime.timedelta(days=day_offset, hours=24-start_hour, minutes=-start_minute, seconds=-start_second)
                # 录音时长 1-3小时（减少时长）
                duration = random.randint(3600, 10800)
                end_time = start_time + datetime.timedelta(seconds=duration)

                avg_volume = random.randint(55, 85)
                file_size = int(duration * 32 * 1024)

                record_id = f"REC_{uuid.uuid4().hex[:8]}"
                filename = f"{device.id}_{start_time.strftime('%Y%m%d_%H%M%S')}.wav"
                filepath = str(self.recording_dir / filename)

                mock_recordings.append({
                    'record_id': record_id,
                    'device_id': device.id,
                    'device_name': device.name,
                    'area_level2': device.area_level2,
                    'area_level3': device.area_level3,
                    'area_level4': device.area_level4,
                    'filename': filename,
                    'filepath': filepath,
                    'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
                    'duration': duration,
                    'file_size': file_size,
                    'avg_volume': avg_volume
                })

        # 批量插入数据库
        inserted = 0
        for rec in mock_recordings:
            try:
                self.cursor.execute('''
                    INSERT INTO recordings 
                    (record_id, device_id, device_name, area_level2, area_level3, area_level4, 
                     filename, filepath, start_time, end_time, duration, file_size, avg_volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (rec['record_id'], rec['device_id'], rec['device_name'],
                      rec['area_level2'], rec['area_level3'], rec['area_level4'],
                      rec['filename'], rec['filepath'], rec['start_time'], rec['end_time'],
                      rec['duration'], rec['file_size'], rec['avg_volume']))
                inserted += 1
            except Exception as e:
                logger.error(f"插入录音失败: {e}")

        self.conn.commit()
        logger.info(f"初始化了 {inserted} 条模拟录音数据")

    def init_mock_recordings(self):
        """初始化模拟录音数据 - 兼容旧调用"""
        self.init_mock_recordings_reduced()

    def init_area_bindings(self):
        """初始化区域绑定 - 每个区域绑定2-3个传感器"""
        bindings_created = 0
        self.area_bindings.clear()

        # 手动配置每个区域绑定的传感器
        bindings_config = [
            # 候车室区域
            ("重庆东站", "候车室", "A区检票口", "A2、A3检票口", ["MIC_001", "MIC_002"]),
            ("重庆东站", "候车室", "A区检票口", "A7、A8检票口", ["MIC_003", "MIC_004"]),
            ("重庆东站", "候车室", "A区检票口", "A12、A13检票口", ["MIC_005", "MIC_006"]),
            ("重庆东站", "候车室", "B区检票口", "B1检票口", ["MIC_007"]),
            ("重庆东站", "候车室", "B区检票口", "B5、B6检票口", ["MIC_008", "MIC_009"]),
            ("重庆东站", "候车室", "B区检票口", "B14、B15检票口", ["MIC_010", "MIC_011"]),
            # 出站口区域
            ("重庆东站", "出站口", "北出站口", "北出站大厅", ["MIC_012", "MIC_013"]),
            ("重庆东站", "出站口", "北出站口", "北出站通道", ["MIC_014"]),
            ("重庆东站", "出站口", "南出站口", "南出站大厅", ["MIC_015", "MIC_016"]),
            ("重庆东站", "出站口", "东出站口", "东出站大厅", ["MIC_017"]),
            # 进站口区域
            ("重庆东站", "进站口", "北进站口", "北进站大厅", ["MIC_018", "MIC_019"]),
            ("重庆东站", "进站口", "北进站口", "北安检区", ["MIC_020"]),
            ("重庆东站", "进站口", "南进站口", "南进站大厅", ["MIC_021", "MIC_022"]),
            ("重庆东站", "进站口", "西进站口", "西进站大厅", ["MIC_023"]),
            # 换乘大厅区域
            ("重庆东站", "换乘大厅", "地铁换乘区", "地铁换乘通道", ["MIC_024", "MIC_025"]),
            ("重庆东站", "换乘大厅", "地铁换乘区", "地铁换乘大厅", ["MIC_026", "MIC_027"]),
        ]

        for station, level2, level3, level4, device_ids in bindings_config:
            binding_id = f"BIND_{station}_{level2}_{level3}_{level4}".replace(" ", "_")
            binding = AreaBinding(
                id=binding_id,
                level1=station,
                level2=level2,
                level3=level3,
                level4=level4,
                device_ids=device_ids
            )
            self.area_bindings[binding_id] = binding

            self.cursor.execute('''
                INSERT OR REPLACE INTO area_bindings 
                (id, level1, level2, level3, level4, device_ids)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (binding_id, station, level2, level3, level4, json.dumps(device_ids)))
            bindings_created += 1

        self.conn.commit()
        logger.info(f"初始化了 {bindings_created} 个区域绑定，每个区域绑定2-3个传感器")

    def start_alert_monitor(self):
        """启动告警监测 - 降低频率"""
        def monitor():
            while True:
                time.sleep(15)  # 从5秒改为15秒
                for device_id, device in self.devices.items():
                    if device.status == DeviceStatus.ONLINE:
                        if random.random() < 0.002:  # 降低变化概率
                            if random.random() < 0.3:
                                device.status = DeviceStatus.ALERT
                                self.update_device_status(device_id, DeviceStatus.ALERT)
                        elif device.status == DeviceStatus.ALERT and random.random() < 0.3:
                            device.status = DeviceStatus.ONLINE
                            self.update_device_status(device_id, DeviceStatus.ONLINE)

        thread = threading.Thread(target=monitor, daemon=True)
        thread.start()
        logger.info("告警监测线程已启动")

    def update_device_status(self, device_id: str, status: DeviceStatus):
        """更新设备状态"""
        try:
            self.cursor.execute('''
                UPDATE devices SET status = ? WHERE device_id = ?
            ''', (status.value, device_id))
            self.conn.commit()

            if self.clients:
                socketio.emit('device_status_change', {
                    'device_id': device_id,
                    'status': status.value
                })
                logger.info(f"设备 {device_id} 状态变更为 {status.value}")
        except Exception as e:
            logger.error(f"更新设备状态失败: {e}")

    def get_area_hierarchy(self) -> Dict:
        """获取区域层级"""
        return self.area_data

    def get_area_bindings(self) -> List[Dict]:
        """获取区域绑定列表（带缓存）"""
        now = time.time()
        if self._bindings_cache and now - self._bindings_cache_time < 5:
            return self._bindings_cache
        
        bindings = []
        for binding in self.area_bindings.values():
            device_names = []
            for device_id in binding.device_ids:
                if device_id in self.devices:
                    device_names.append(self.devices[device_id].name)

            bindings.append({
                'id': binding.id,
                'level1': binding.level1,
                'level2': binding.level2,
                'level3': binding.level3,
                'device_ids': binding.device_ids,
                'device_names': device_names,
                'device_count': len(binding.device_ids)
            })
        
        self._bindings_cache = bindings
        self._bindings_cache_time = now
        return bindings

    def get_devices_by_area(self, level3: str = None, level4: str = None) -> List[Dict]:
        """根据区域获取拾音器列表"""
        devices = []
        for device in self.devices.values():
            if level3 and device.area_level3 != level3:
                continue
            if level4 and device.area_level4 != level4:
                continue
            devices.append({
                'id': device.id,
                'name': device.name,
                'status': device.status.value,
                'current_volume': self.device_volumes.get(device.id, 0),
                'area_level2': device.area_level2,
                'area_level3': device.area_level3,
            })
        return devices

    def get_devices(self) -> List[Dict]:
        """获取所有拾音器"""
        devices = []
        for device in self.devices.values():
            devices.append({
                'id': device.id,
                'name': device.name,
                'station': device.station,
                'area_level2': device.area_level2,
                'area_level3': device.area_level3,
                'area_level4': device.area_level4,
                'status': device.status.value,
                'ip': device.ip,
                'mac': device.mac,
                'last_heartbeat': device.last_heartbeat.isoformat() if device.last_heartbeat else None,
                'current_volume': self.device_volumes.get(device.id, 0)
            })
        return devices

    @cached(timeout=2)
    def get_recordings_by_device_and_time(self, device_name: str = None, level3: str = None,
                                         start_time: str = None, end_time: str = None) -> List[Dict]:
        """根据传感器名称、区域名称和时间段获取录音（每个传感器一条整体录音）"""
        query = '''
            SELECT r.*, d.status 
            FROM recordings r
            JOIN devices d ON r.device_id = d.device_id
            WHERE 1=1
        '''
        params = []

        if level3 and level3 != '全部' and level3 != '':
            query += ' AND d.area_level3 = ?'
            params.append(level3)

        if device_name and device_name != '':
            query += ' AND d.device_name LIKE ?'
            params.append(f'%{device_name}%')

        if start_time:
            query += ' AND r.start_time >= ?'
            params.append(start_time)
        if end_time:
            query += ' AND r.end_time <= ?'
            params.append(end_time)

        query += ' ORDER BY r.start_time DESC LIMIT 200'  # 限制返回数量

        try:
            self.cursor.execute(query, params)
            records = self.cursor.fetchall()
            columns = [description[0] for description in self.cursor.description]

            device_record_map = {}
            for rec in records:
                device_id = rec[columns.index('device_id')]
                if device_id not in device_record_map:
                    device_record_map[device_id] = {
                        'record_id': rec[columns.index('record_id')],
                        'device_id': device_id,
                        'device_name': rec[columns.index('device_name')],
                        'area_level2': rec[columns.index('area_level2')],
                        'area_level3': rec[columns.index('area_level3')],
                        'start_time': rec[columns.index('start_time')],
                        'end_time': rec[columns.index('end_time')],
                        'duration': rec[columns.index('duration')],
                        'avg_volume': rec[columns.index('avg_volume')],
                        'status': rec[columns.index('status')] if 'status' in columns else 'online'
                    }

            return list(device_record_map.values())
        except Exception as e:
            logger.error(f"查询录音失败: {e}")
            return []

    @cached(timeout=2)
    def get_recordings_by_time_range_with_segments(self, device_name: str = None, level3: str = None,
                                                     start_time: str = None, end_time: str = None) -> List[Dict]:
        """获取指定时间段内的所有录音片段"""
        query = '''
            SELECT r.*, d.status 
            FROM recordings r
            JOIN devices d ON r.device_id = d.device_id
            WHERE 1=1
        '''
        params = []

        if level3 and level3 != '全部' and level3 != '':
            query += ' AND d.area_level3 = ?'
            params.append(level3)

        if device_name and device_name != '':
            query += ' AND d.device_name LIKE ?'
            params.append(f'%{device_name}%')

        if start_time:
            query += ' AND r.start_time >= ?'
            params.append(start_time)
        if end_time:
            query += ' AND r.end_time <= ?'
            params.append(end_time)

        query += ' ORDER BY r.start_time ASC LIMIT 500'

        try:
            self.cursor.execute(query, params)
            records = self.cursor.fetchall()
            columns = [description[0] for description in self.cursor.description]

            result = []
            for rec in records:
                result.append({
                    'record_id': rec[columns.index('record_id')],
                    'device_id': rec[columns.index('device_id')],
                    'device_name': rec[columns.index('device_name')],
                    'area_level2': rec[columns.index('area_level2')],
                    'area_level3': rec[columns.index('area_level3')],
                    'start_time': rec[columns.index('start_time')],
                    'end_time': rec[columns.index('end_time')],
                    'duration': rec[columns.index('duration')],
                    'avg_volume': rec[columns.index('avg_volume')],
                    'status': rec[columns.index('status')] if 'status' in columns else 'online'
                })
            return result
        except Exception as e:
            logger.error(f"查询录音片段失败: {e}")
            return []

    def bind_area_device(self, level3: str, level4: str, device_ids: List[str]) -> bool:
        """绑定区域和拾音器"""
        try:
            station = "重庆东站"
            level2 = None
            for l2, l3_map in self.area_data[station].items():
                if level3 in l3_map:
                    level2 = l2
                    break

            if not level2:
                logger.error(f"未找到区域: {level3}")
                return False

            binding_id = f"BIND_{station}_{level2}_{level3}_{level4}".replace(" ", "_")

            self.cursor.execute('''
                INSERT OR REPLACE INTO area_bindings 
                (id, level1, level2, level3, level4, device_ids)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (binding_id, station, level2, level3, level4, json.dumps(device_ids)))
            self.conn.commit()

            if binding_id in self.area_bindings:
                self.area_bindings[binding_id].device_ids = device_ids
            else:
                self.area_bindings[binding_id] = AreaBinding(
                    id=binding_id,
                    level1=station,
                    level2=level2,
                    level3=level3,
                    level4=level4,
                    device_ids=device_ids
                )
            
            # 清除缓存
            self._bindings_cache = None

            logger.info(f"绑定成功: {level3} > {level4}, 绑定 {len(device_ids)} 个设备")
            return True
        except Exception as e:
            logger.error(f"绑定失败: {e}")
            return False

    def unbind_area_device(self, binding_id: str) -> bool:
        """解除区域绑定"""
        try:
            self.cursor.execute('DELETE FROM area_bindings WHERE id = ?', (binding_id,))
            self.conn.commit()

            if binding_id in self.area_bindings:
                del self.area_bindings[binding_id]
            
            # 清除缓存
            self._bindings_cache = None

            logger.info(f"解绑成功: {binding_id}")
            return True
        except Exception as e:
            logger.error(f"解绑失败: {e}")
            return False

    def get_unbound_devices_by_area(self, level3: str = None, level4: str = None) -> List[Dict]:
        """获取指定区域未绑定的拾音器"""
        bound_ids = set()
        for binding in self.area_bindings.values():
            bound_ids.update(binding.device_ids)

        unbound = []
        for device in self.devices.values():
            if device.id not in bound_ids:
                if level3 and device.area_level3 != level3:
                    continue
                if level4 and device.area_level4 != level4:
                    continue
                unbound.append({
                    'id': device.id,
                    'name': device.name,
                    'area_level2': device.area_level2,
                    'area_level3': device.area_level3,
                    'area_level4': device.area_level4,
                    'status': device.status.value
                })

        return unbound

    def get_unbound_devices(self) -> List[Dict]:
        """获取所有未绑定的拾音器"""
        bound_ids = set()
        for binding in self.area_bindings.values():
            bound_ids.update(binding.device_ids)

        unbound = []
        for device in self.devices.values():
            if device.id not in bound_ids:
                unbound.append({
                    'id': device.id,
                    'name': device.name,
                    'area_level2': device.area_level2,
                    'area_level3': device.area_level3,
                    'area_level4': device.area_level4,
                    'status': device.status.value
                })

        return unbound

    def get_statistics(self) -> Dict:
        """获取统计信息（带缓存）"""
        now = time.time()
        if self._stats_cache and now - self._stats_cache_time < 3:
            return self._stats_cache
        
        devices = self.get_devices()
        online_count = len([d for d in devices if d['status'] == 'online'])
        offline_count = len([d for d in devices if d['status'] == 'offline'])
        alert_count = len([d for d in devices if d['status'] == 'alert'])

        result = {
            'total_devices': len(devices),
            'online_devices': online_count,
            'offline_devices': offline_count,
            'alert_devices': alert_count
        }
        
        self._stats_cache = result
        self._stats_cache_time = now
        return result

    def start(self):
        """启动系统"""
        self.is_recording = True
        logger.info("系统已启动")

    def stop(self):
        """停止系统"""
        self.is_recording = False
        if self.p:
            self.p.terminate()
        self.conn.close()
        logger.info("系统已停止")


# 全局系统实例
audio_system = AudioMonitorSystem()


# Socket.IO事件处理
@socketio.on('connect')
def handle_connect():
    logger.info(f"客户端连接: {request.sid}")
    audio_system.clients.add(request.sid)
    emit('connected', {'message': 'Connected to railway broadcast monitor'})


@socketio.on('disconnect')
def handle_disconnect():
    logger.info(f"客户端断开: {request.sid}")
    audio_system.clients.discard(request.sid)


# REST API路由
@app.route('/')
def index():
    """主页"""
    return render_template('index.html')


@app.route('/api/area/hierarchy')
def get_area_hierarchy():
    """获取区域层级"""
    return jsonify({'success': True, 'data': audio_system.get_area_hierarchy()})


@app.route('/api/area/bindings')
def get_area_bindings():
    """获取区域绑定列表（不包含详细位置）"""
    bindings = audio_system.get_area_bindings()
    return jsonify({'success': True, 'data': bindings})


@app.route('/api/area/bindings/<binding_id>', methods=['DELETE'])
def unbind_area_binding(binding_id):
    """解除区域绑定"""
    success = audio_system.unbind_area_device(binding_id)
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '解绑失败'}), 400


@app.route('/api/area/devices')
def get_devices_by_area():
    """根据区域获取拾音器（不包含详细位置）"""
    level3 = request.args.get('level3')
    level4 = request.args.get('level4')
    devices = audio_system.get_devices_by_area(level3, level4)
    return jsonify({'success': True, 'data': devices})


@app.route('/api/area/bind', methods=['POST'])
def bind_area_device():
    """绑定区域和拾音器"""
    data = request.json
    success = audio_system.bind_area_device(
        data.get('level3'),
        data.get('level4'),
        data.get('device_ids', [])
    )
    if success:
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '绑定失败'}), 400


@app.route('/api/devices/unbound')
def get_unbound_devices():
    """获取所有未绑定的拾音器"""
    devices = audio_system.get_unbound_devices()
    return jsonify({'success': True, 'data': devices})


@app.route('/api/devices/unbound/by-area')
def get_unbound_devices_by_area():
    """根据区域获取未绑定的拾音器"""
    level3 = request.args.get('level3')
    level4 = request.args.get('level4')
    devices = audio_system.get_unbound_devices_by_area(level3, level4)
    return jsonify({'success': True, 'data': devices})


@app.route('/api/devices')
def get_devices():
    """获取所有拾音器"""
    devices = audio_system.get_devices()
    return jsonify({'success': True, 'data': devices})


@app.route('/api/recordings/by-device-time')
def get_recordings_by_device_time():
    """根据传感器名称、区域名称和时间段获取录音"""
    device_name = request.args.get('device_name')
    level3 = request.args.get('level3')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')

    recordings = audio_system.get_recordings_by_device_and_time(device_name, level3, start_time, end_time)
    return jsonify({'success': True, 'data': recordings})


@app.route('/api/recordings/time-segments')
def get_recordings_time_segments():
    """获取时间段内的所有录音片段"""
    device_name = request.args.get('device_name')
    level3 = request.args.get('level3')
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')

    recordings = audio_system.get_recordings_by_time_range_with_segments(device_name, level3, start_time, end_time)
    return jsonify({'success': True, 'data': recordings})


@app.route('/api/statistics')
def get_statistics():
    """获取统计信息"""
    stats = audio_system.get_statistics()
    return jsonify({'success': True, 'data': stats})


if __name__ == '__main__':
    audio_system.start()
    # 使用更少的worker，降低资源消耗
    socketio.run(app, host='0.0.0.0', port=5003, debug=False, allow_unsafe_werkzeug=True)
