# app.py - 车站休息设施管理系统（完整版）
from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd
from io import BytesIO
import datetime
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)

# 配置图片上传
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ==================== 数据结构 ====================
# 国铁 -> 路局 -> 站段 -> 车站 的树形结构
# 车站等级使用：一级、二级、三级、四级
railway_data = {
    "国铁集团": {
        "北京局": {
            "北京车务段": {
                "北京南站": {
                    "station_name": "北京南站",
                    "basic_info": {
                        "省": "北京市",
                        "市": "北京市",
                        "区": "丰台区",
                        "街道": "南站街道",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "22:00",
                        "服务人员数量": 12,
                        "联系电话_座机": "010-67561234",
                        "联系电话_手机": "13800138000",
                        "独立停车区": "有",
                        "停车位数量": 50,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "北京铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室（南）"},
                        {"type": "商务候车室", "count": 2, "name": "商务候车室（北）"},
                        {"type": "商务座候车区", "count": 2, "name": "商务座候车区1"},
                        {"type": "商务座候车区", "count": 2, "name": "商务座候车区2"},
                        {"type": "商业候车室", "count": 1, "name": "商业候车室"}
                    ]
                },
                "北京西站": {
                    "station_name": "北京西站",
                    "basic_info": {
                        "省": "北京市",
                        "市": "北京市",
                        "区": "海淀区",
                        "街道": "羊坊店街道",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "23:00",
                        "服务人员数量": 10,
                        "联系电话_座机": "010-51861234",
                        "联系电话_手机": "13900139000",
                        "独立停车区": "有",
                        "停车位数量": 80,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "北京铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室（南）"},
                        {"type": "商务候车室", "count": 2, "name": "商务候车室（北）"},
                        {"type": "商务座候车区", "count": 1, "name": "商务座候车区"},
                        {"type": "商业候车室", "count": 1, "name": "商业候车室"}
                    ]
                },
                "北京站": {
                    "station_name": "北京站",
                    "basic_info": {
                        "省": "北京市",
                        "市": "北京市",
                        "区": "东城区",
                        "街道": "建国门街道",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "22:00",
                        "服务人员数量": 8,
                        "联系电话_座机": "010-51834567",
                        "联系电话_手机": "13700137000",
                        "独立停车区": "有",
                        "停车位数量": 40,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "北京铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 1, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 1, "name": "商务座候车区"},
                        {"type": "商业候车室", "count": 1, "name": "商业候车室"}
                    ]
                },
                "北京北站": {
                    "station_name": "北京北站",
                    "basic_info": {
                        "省": "北京市",
                        "市": "北京市",
                        "区": "西城区",
                        "街道": "德胜街道",
                        "车站等级": "二级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "21:00",
                        "服务人员数量": 8,
                        "联系电话_座机": "010-51834567",
                        "联系电话_手机": "13700137000",
                        "独立停车区": "有",
                        "停车位数量": 40,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "北京铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 1, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 1, "name": "商务座候车区"}
                    ]
                }
            },
            "石家庄车务段": {
                "石家庄站": {
                    "station_name": "石家庄站",
                    "basic_info": {
                        "省": "河北省",
                        "市": "石家庄市",
                        "区": "桥西区",
                        "街道": "中华南大街",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "22:30",
                        "服务人员数量": 10,
                        "联系电话_座机": "0311-87928888",
                        "联系电话_手机": "13700337000",
                        "独立停车区": "有",
                        "停车位数量": 60,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "北京铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室（南）"},
                        {"type": "商务座候车区", "count": 1, "name": "商务座候车区"},
                        {"type": "商业候车室", "count": 1, "name": "商业候车室"}
                    ]
                }
            },
            "天津车务段": {
                "天津站": {
                    "station_name": "天津站",
                    "basic_info": {
                        "省": "天津市",
                        "市": "天津市",
                        "区": "河北区",
                        "街道": "新纬路",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "23:00",
                        "服务人员数量": 12,
                        "联系电话_座机": "022-26188888",
                        "联系电话_手机": "13800238000",
                        "独立停车区": "有",
                        "停车位数量": 80,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "北京铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 2, "name": "商务座候车区"},
                        {"type": "商业候车室", "count": 1, "name": "商业候车室"}
                    ]
                }
            }
        },
        "上海局": {
            "上海车务段": {
                "上海虹桥站": {
                    "station_name": "上海虹桥站",
                    "basic_info": {
                        "省": "上海市",
                        "市": "上海市",
                        "区": "闵行区",
                        "街道": "虹桥街道",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "05:30",
                        "营业时间_结束": "23:30",
                        "服务人员数量": 15,
                        "联系电话_座机": "021-51234567",
                        "联系电话_手机": "13700137000",
                        "独立停车区": "有",
                        "停车位数量": 120,
                        "登车提醒时间": 20,
                        "建设情况": "已建成",
                        "出资情况": "合资",
                        "资金来源": "专项资金",
                        "建设单位": "上海铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 3, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 2, "name": "商务座候车区"},
                        {"type": "商业候车室", "count": 2, "name": "商业候车室"}
                    ]
                },
                "杭州东站": {
                    "station_name": "杭州东站",
                    "basic_info": {
                        "省": "浙江省",
                        "市": "杭州市",
                        "区": "江干区",
                        "街道": "彭埠街道",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "22:30",
                        "服务人员数量": 12,
                        "联系电话_座机": "0571-56789012",
                        "联系电话_手机": "13800138001",
                        "独立停车区": "有",
                        "停车位数量": 90,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "上海铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 2, "name": "商务座候车区"}
                    ]
                },
                "南京南站": {
                    "station_name": "南京南站",
                    "basic_info": {
                        "省": "江苏省",
                        "市": "南京市",
                        "区": "雨花台区",
                        "街道": "玉兰路",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "22:00",
                        "服务人员数量": 14,
                        "联系电话_座机": "025-58800000",
                        "联系电话_手机": "13900139001",
                        "独立停车区": "有",
                        "停车位数量": 100,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "上海铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 2, "name": "商务座候车区"},
                        {"type": "商业候车室", "count": 1, "name": "商业候车室"}
                    ]
                }
            }
        },
        "成都局": {
            "成都车务段": {
                "成都东站": {
                    "station_name": "成都东站",
                    "basic_info": {
                        "省": "四川省",
                        "市": "成都市",
                        "区": "成华区",
                        "街道": "保和街道",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:30",
                        "营业时间_结束": "22:30",
                        "服务人员数量": 8,
                        "联系电话_座机": "028-86451234",
                        "联系电话_手机": "13600136000",
                        "独立停车区": "有",
                        "停车位数量": 60,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "成都铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 2, "name": "商务座候车区"},
                        {"type": "商业候车室", "count": 1, "name": "商业候车室"}
                    ]
                }
            },
            "重庆车务段": {
                "重庆北站": {
                    "station_name": "重庆北站",
                    "basic_info": {
                        "省": "重庆市",
                        "市": "重庆市",
                        "区": "渝北区",
                        "街道": "龙头寺",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "06:00",
                        "营业时间_结束": "22:00",
                        "服务人员数量": 10,
                        "联系电话_座机": "023-61850000",
                        "联系电话_手机": "13700137001",
                        "独立停车区": "有",
                        "停车位数量": 70,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "成都铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 2, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 1, "name": "商务座候车区"}
                    ]
                }
            },
            "贵阳车务段": {
                "贵阳北站": {
                    "station_name": "贵阳北站",
                    "basic_info": {
                        "省": "贵州省",
                        "市": "贵阳市",
                        "区": "观山湖区",
                        "街道": "阳关大道",
                        "车站等级": "一级",
                        "商务候车室类型": "商务候车室",
                        "专用进站通道": "有",
                        "专用出站通道": "有",
                        "有wifi": "有",
                        "营业时间_开始": "07:00",
                        "营业时间_结束": "21:30",
                        "服务人员数量": 8,
                        "联系电话_座机": "0851-88180000",
                        "联系电话_手机": "13800138002",
                        "独立停车区": "有",
                        "停车位数量": 50,
                        "登车提醒时间": 15,
                        "建设情况": "已建成",
                        "出资情况": "路局出资",
                        "资金来源": "专项资金",
                        "建设单位": "成都铁路建设集团"
                    },
                    "open_areas": [],
                    "large_halls": [],
                    "medium_halls": [],
                    "small_halls": [],
                    "meeting_rooms": [],
                    "waiting_rooms": [
                        {"type": "商务候车室", "count": 1, "name": "商务候车室"},
                        {"type": "商务座候车区", "count": 1, "name": "商务座候车区"}
                    ]
                }
            }
        }
    }
}

current_station = ""
current_path = {"railway": "国铁集团", "bureau": "北京局", "section": "北京车务段", "station": "北京南站"}

# ID计数器
id_counters = {}


def init_counters_for_station(station_key):
    if station_key not in id_counters:
        id_counters[station_key] = {"open_areas": 1, "large_halls": 1, "medium_halls": 1, "small_halls": 1,
                                    "meeting_rooms": 1}


def get_station_by_path(railway, bureau, section, station):
    try:
        return railway_data[railway][bureau][section][station]
    except:
        return None


def set_current_station_by_path(railway, bureau, section, station):
    global current_station, current_path
    current_path = {"railway": railway, "bureau": bureau, "section": section, "station": station}
    current_station = station


def init_sample_data():
    # 为北京南站添加示例设施数据
    station = railway_data["国铁集团"]["北京局"]["北京车务段"]["北京南站"]
    init_counters_for_station("北京南站")

    station["open_areas"] = [
        {"id": 1, "name": "VIP贵宾休息区", "area": 150, "has_toilet": "有", "has_kitchen": "有", "sofa_count": 25,
         "seat_count": 50, "price": 128, "position": "南侧2层", "door_photo": "", "business_mode": "自营",
         "business_subject": "北京南站", "fee_standard": "128元/人/次", "contract_end_date": "2026-12-31",
         "contract_amount": 500000, "has_naming": "是", "naming_unit": "中国银行"},
        {"id": 2, "name": "商务精英区", "area": 100, "has_toilet": "有", "has_kitchen": "无", "sofa_count": 15,
         "seat_count": 35, "price": 88, "position": "北侧1层", "door_photo": "", "business_mode": "合作",
         "business_subject": "北京商务服务公司", "fee_standard": "88元/人/次", "contract_end_date": "2025-12-31",
         "contract_amount": 300000, "has_naming": "否", "naming_unit": ""},
    ]
    station["large_halls"] = [
        {"id": 1, "name": "大型商务厅A", "area": 200, "has_toilet": "有", "has_kitchen": "有", "sofa_count": 40,
         "seat_count": 80, "price_per_hour": 300, "position": "东侧3层", "door_photo": "", "business_mode": "自营",
         "business_subject": "北京南站", "fee_standard": "300元/小时", "contract_end_date": "2026-06-30",
         "contract_amount": 800000, "has_naming": "是", "naming_unit": "华为"},
    ]
    station["medium_halls"] = [
        {"id": 1, "name": "中型会议室厅", "area": 120, "has_toilet": "有", "has_kitchen": "无", "sofa_count": 20,
         "seat_count": 45, "price_per_hour": 180, "position": "西侧2层", "door_photo": "", "business_mode": "委托服务",
         "business_subject": "北京会议服务公司", "fee_standard": "180元/小时", "contract_end_date": "2025-10-31",
         "contract_amount": 200000, "has_naming": "否", "naming_unit": ""},
    ]
    station["small_halls"] = [
        {"id": 1, "name": "小型私密厅", "area": 60, "has_toilet": "有", "has_kitchen": "无", "sofa_count": 10,
         "seat_count": 20, "price_per_hour": 100, "position": "南侧1层", "door_photo": "", "business_mode": "自营",
         "business_subject": "北京南站", "fee_standard": "100元/小时", "contract_end_date": "2026-12-31",
         "contract_amount": 150000, "has_naming": "否", "naming_unit": ""},
    ]
    station["meeting_rooms"] = [
        {"id": 1, "name": "董事会议室", "area": 80, "has_toilet": "有", "has_kitchen": "有", "seat_count": 25,
         "price_per_hour": 250, "position": "中央5层", "door_photo": "", "business_mode": "自营",
         "business_subject": "北京南站", "fee_standard": "250元/小时", "contract_end_date": "2027-06-30",
         "contract_amount": 350000, "has_naming": "是", "naming_unit": "招商银行"},
    ]
    id_counters["北京南站"] = {"open_areas": 3, "large_halls": 2, "medium_halls": 2, "small_halls": 2,
                               "meeting_rooms": 2}

    # 为北京西站添加示例设施数据
    station2 = railway_data["国铁集团"]["北京局"]["北京车务段"]["北京西站"]
    init_counters_for_station("北京西站")
    station2["open_areas"] = [
        {"id": 1, "name": "VIP休息区", "area": 120, "has_toilet": "有", "has_kitchen": "有", "sofa_count": 20,
         "seat_count": 40, "price": 108, "position": "南侧2层", "door_photo": "", "business_mode": "自营",
         "business_subject": "北京西站", "fee_standard": "108元/人/次", "contract_end_date": "2026-12-31",
         "contract_amount": 400000, "has_naming": "是", "naming_unit": "工商银行"},
    ]
    station2["large_halls"] = [
        {"id": 1, "name": "大型商务厅", "area": 180, "has_toilet": "有", "has_kitchen": "有", "sofa_count": 35,
         "seat_count": 70, "price_per_hour": 280, "position": "东侧3层", "door_photo": "", "business_mode": "自营",
         "business_subject": "北京西站", "fee_standard": "280元/小时", "contract_end_date": "2026-06-30",
         "contract_amount": 700000, "has_naming": "是", "naming_unit": "华为"},
    ]

    # 为石家庄站添加示例数据
    station_shijiazhuang = railway_data["国铁集团"]["北京局"]["石家庄车务段"]["石家庄站"]
    init_counters_for_station("石家庄站")
    station_shijiazhuang["open_areas"] = [
        {"id": 1, "name": "VIP休息区", "area": 100, "has_toilet": "有", "has_kitchen": "有", "sofa_count": 18,
         "seat_count": 35, "price": 98, "position": "南侧2层", "door_photo": "", "business_mode": "自营",
         "business_subject": "石家庄站", "fee_standard": "98元/人/次", "contract_end_date": "2026-12-31",
         "contract_amount": 350000, "has_naming": "是", "naming_unit": "农业银行"},
    ]

    # 为天津站添加示例数据
    station_tianjin = railway_data["国铁集团"]["北京局"]["天津车务段"]["天津站"]
    init_counters_for_station("天津站")
    station_tianjin["open_areas"] = [
        {"id": 1, "name": "商务休息区", "area": 130, "has_toilet": "有", "has_kitchen": "有", "sofa_count": 22,
         "seat_count": 45, "price": 118, "position": "北侧2层", "door_photo": "", "business_mode": "自营",
         "business_subject": "天津站", "fee_standard": "118元/人/次", "contract_end_date": "2026-12-31",
         "contract_amount": 450000, "has_naming": "是", "naming_unit": "交通银行"},
    ]

    # 为上海虹桥站添加示例数据
    station_shanghai = railway_data["国铁集团"]["上海局"]["上海车务段"]["上海虹桥站"]
    init_counters_for_station("上海虹桥站")
    station_shanghai["open_areas"] = [
        {"id": 1, "name": "VIP贵宾区", "area": 200, "has_toilet": "有", "has_kitchen": "有", "sofa_count": 30,
         "seat_count": 60, "price": 158, "position": "南侧2层", "door_photo": "", "business_mode": "自营",
         "business_subject": "上海虹桥站", "fee_standard": "158元/人/次", "contract_end_date": "2026-12-31",
         "contract_amount": 600000, "has_naming": "是", "naming_unit": "建设银行"},
    ]


# ==================== 图片上传API ====================
@app.route('/api/upload_photo', methods=['POST'])
def upload_photo():
    if 'photo' not in request.files:
        return jsonify({"status": "error", "message": "没有文件"})
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"status": "error", "message": "文件名为空"})
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        return jsonify({"status": "success", "url": f"/static/uploads/{filename}"})
    return jsonify({"status": "error", "message": "文件类型不支持"})


# ==================== Excel导出功能 ====================
@app.route('/api/export_all_excel')
def export_all_excel():
    output = BytesIO()
    all_data = []

    for railway, bureaus in railway_data.items():
        for bureau, sections in bureaus.items():
            for section, stations in sections.items():
                for station_name, station in stations.items():
                    basic = station['basic_info']

                    for area in station['open_areas']:
                        all_data.append({
                            '国铁': railway, '路局': bureau, '站段': section, '车站名称': station_name,
                            '省份': basic.get('省', ''), '城市': basic.get('市', ''), '区县': basic.get('区', ''),
                            '街道': basic.get('街道', ''),
                            '车站等级': basic.get('车站等级', ''), '商务候车室类型': basic.get('商务候车室类型', ''),
                            '专用进站通道': basic.get('专用进站通道', ''),
                            '专用出站通道': basic.get('专用出站通道', ''),
                            '有wifi': basic.get('有wifi', ''),
                            '营业时间': f"{basic.get('营业时间_开始', '')}-{basic.get('营业时间_结束', '')}",
                            '服务人员数量': basic.get('服务人员数量', ''), '联系电话': basic.get('联系电话_座机', ''),
                            '独立停车区': basic.get('独立停车区', ''), '停车位数量': basic.get('停车位数量', ''),
                            '登车提醒时间': basic.get('登车提醒时间', ''), '建设情况': basic.get('建设情况', ''),
                            '出资情况': basic.get('出资情况', ''), '资金来源': basic.get('资金来源', ''),
                            '建设单位': basic.get('建设单位', ''), '设施类型': '开放休息区',
                            '设施名称': area['name'], '面积(㎡)': area['area'], '是否有卫生间': area['has_toilet'],
                            '是否有操作间': area['has_kitchen'], '沙发数量': area.get('sofa_count', ''),
                            '座位数量': area['seat_count'], '价格': f"{area['price']}元/人/次",
                            '位置': area.get('position', ''), '经营模式': area.get('business_mode', ''),
                            '经营主体': area.get('business_subject', ''), '经营收费标准': area.get('fee_standard', ''),
                            '合同到期时间': area.get('contract_end_date', ''),
                            '合同金额': area.get('contract_amount', ''),
                            '是否有冠名候车室': area.get('has_naming', ''), '冠名单位': area.get('naming_unit', '')
                        })

                    for hall in station['large_halls']:
                        all_data.append({
                            '国铁': railway, '路局': bureau, '站段': section, '车站名称': station_name,
                            '省份': basic.get('省', ''), '城市': basic.get('市', ''), '区县': basic.get('区', ''),
                            '街道': basic.get('街道', ''),
                            '车站等级': basic.get('车站等级', ''), '商务候车室类型': basic.get('商务候车室类型', ''),
                            '专用进站通道': basic.get('专用进站通道', ''),
                            '专用出站通道': basic.get('专用出站通道', ''),
                            '有wifi': basic.get('有wifi', ''),
                            '营业时间': f"{basic.get('营业时间_开始', '')}-{basic.get('营业时间_结束', '')}",
                            '服务人员数量': basic.get('服务人员数量', ''), '联系电话': basic.get('联系电话_座机', ''),
                            '独立停车区': basic.get('独立停车区', ''), '停车位数量': basic.get('停车位数量', ''),
                            '登车提醒时间': basic.get('登车提醒时间', ''), '建设情况': basic.get('建设情况', ''),
                            '出资情况': basic.get('出资情况', ''), '资金来源': basic.get('资金来源', ''),
                            '建设单位': basic.get('建设单位', ''), '设施类型': '大型休息厅',
                            '设施名称': hall['name'], '面积(㎡)': hall['area'], '是否有卫生间': hall['has_toilet'],
                            '是否有操作间': hall['has_kitchen'], '沙发数量': hall.get('sofa_count', ''),
                            '座位数量': hall['seat_count'], '价格': f"{hall['price_per_hour']}元/小时",
                            '位置': hall.get('position', ''), '经营模式': hall.get('business_mode', ''),
                            '经营主体': hall.get('business_subject', ''), '经营收费标准': hall.get('fee_standard', ''),
                            '合同到期时间': hall.get('contract_end_date', ''),
                            '合同金额': hall.get('contract_amount', ''),
                            '是否有冠名候车室': hall.get('has_naming', ''), '冠名单位': hall.get('naming_unit', '')
                        })

                    for hall in station['medium_halls']:
                        all_data.append({
                            '国铁': railway, '路局': bureau, '站段': section, '车站名称': station_name,
                            '省份': basic.get('省', ''), '城市': basic.get('市', ''), '区县': basic.get('区', ''),
                            '街道': basic.get('街道', ''),
                            '车站等级': basic.get('车站等级', ''), '商务候车室类型': basic.get('商务候车室类型', ''),
                            '专用进站通道': basic.get('专用进站通道', ''),
                            '专用出站通道': basic.get('专用出站通道', ''),
                            '有wifi': basic.get('有wifi', ''),
                            '营业时间': f"{basic.get('营业时间_开始', '')}-{basic.get('营业时间_结束', '')}",
                            '服务人员数量': basic.get('服务人员数量', ''), '联系电话': basic.get('联系电话_座机', ''),
                            '独立停车区': basic.get('独立停车区', ''), '停车位数量': basic.get('停车位数量', ''),
                            '登车提醒时间': basic.get('登车提醒时间', ''), '建设情况': basic.get('建设情况', ''),
                            '出资情况': basic.get('出资情况', ''), '资金来源': basic.get('资金来源', ''),
                            '建设单位': basic.get('建设单位', ''), '设施类型': '中型休息厅',
                            '设施名称': hall['name'], '面积(㎡)': hall['area'], '是否有卫生间': hall['has_toilet'],
                            '是否有操作间': hall['has_kitchen'], '沙发数量': hall.get('sofa_count', ''),
                            '座位数量': hall['seat_count'], '价格': f"{hall['price_per_hour']}元/小时",
                            '位置': hall.get('position', ''), '经营模式': hall.get('business_mode', ''),
                            '经营主体': hall.get('business_subject', ''), '经营收费标准': hall.get('fee_standard', ''),
                            '合同到期时间': hall.get('contract_end_date', ''),
                            '合同金额': hall.get('contract_amount', ''),
                            '是否有冠名候车室': hall.get('has_naming', ''), '冠名单位': hall.get('naming_unit', '')
                        })

                    for hall in station['small_halls']:
                        all_data.append({
                            '国铁': railway, '路局': bureau, '站段': section, '车站名称': station_name,
                            '省份': basic.get('省', ''), '城市': basic.get('市', ''), '区县': basic.get('区', ''),
                            '街道': basic.get('街道', ''),
                            '车站等级': basic.get('车站等级', ''), '商务候车室类型': basic.get('商务候车室类型', ''),
                            '专用进站通道': basic.get('专用进站通道', ''),
                            '专用出站通道': basic.get('专用出站通道', ''),
                            '有wifi': basic.get('有wifi', ''),
                            '营业时间': f"{basic.get('营业时间_开始', '')}-{basic.get('营业时间_结束', '')}",
                            '服务人员数量': basic.get('服务人员数量', ''), '联系电话': basic.get('联系电话_座机', ''),
                            '独立停车区': basic.get('独立停车区', ''), '停车位数量': basic.get('停车位数量', ''),
                            '登车提醒时间': basic.get('登车提醒时间', ''), '建设情况': basic.get('建设情况', ''),
                            '出资情况': basic.get('出资情况', ''), '资金来源': basic.get('资金来源', ''),
                            '建设单位': basic.get('建设单位', ''), '设施类型': '小型休息厅',
                            '设施名称': hall['name'], '面积(㎡)': hall['area'], '是否有卫生间': hall['has_toilet'],
                            '是否有操作间': hall['has_kitchen'], '沙发数量': hall.get('sofa_count', ''),
                            '座位数量': hall['seat_count'], '价格': f"{hall['price_per_hour']}元/小时",
                            '位置': hall.get('position', ''), '经营模式': hall.get('business_mode', ''),
                            '经营主体': hall.get('business_subject', ''), '经营收费标准': hall.get('fee_standard', ''),
                            '合同到期时间': hall.get('contract_end_date', ''),
                            '合同金额': hall.get('contract_amount', ''),
                            '是否有冠名候车室': hall.get('has_naming', ''), '冠名单位': hall.get('naming_unit', '')
                        })

                    for room in station['meeting_rooms']:
                        all_data.append({
                            '国铁': railway, '路局': bureau, '站段': section, '车站名称': station_name,
                            '省份': basic.get('省', ''), '城市': basic.get('市', ''), '区县': basic.get('区', ''),
                            '街道': basic.get('街道', ''),
                            '车站等级': basic.get('车站等级', ''), '商务候车室类型': basic.get('商务候车室类型', ''),
                            '专用进站通道': basic.get('专用进站通道', ''),
                            '专用出站通道': basic.get('专用出站通道', ''),
                            '有wifi': basic.get('有wifi', ''),
                            '营业时间': f"{basic.get('营业时间_开始', '')}-{basic.get('营业时间_结束', '')}",
                            '服务人员数量': basic.get('服务人员数量', ''), '联系电话': basic.get('联系电话_座机', ''),
                            '独立停车区': basic.get('独立停车区', ''), '停车位数量': basic.get('停车位数量', ''),
                            '登车提醒时间': basic.get('登车提醒时间', ''), '建设情况': basic.get('建设情况', ''),
                            '出资情况': basic.get('出资情况', ''), '资金来源': basic.get('资金来源', ''),
                            '建设单位': basic.get('建设单位', ''), '设施类型': '会议室',
                            '设施名称': room['name'], '面积(㎡)': room['area'], '是否有卫生间': room['has_toilet'],
                            '是否有操作间': room['has_kitchen'], '沙发数量': '', '座位数量': room['seat_count'],
                            '价格': f"{room['price_per_hour']}元/小时",
                            '位置': room.get('position', ''), '经营模式': room.get('business_mode', ''),
                            '经营主体': room.get('business_subject', ''), '经营收费标准': room.get('fee_standard', ''),
                            '合同到期时间': room.get('contract_end_date', ''),
                            '合同金额': room.get('contract_amount', ''),
                            '是否有冠名候车室': room.get('has_naming', ''), '冠名单位': room.get('naming_unit', '')
                        })

    df = pd.DataFrame(all_data)
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='车站设施数据汇总', index=False)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True,
                     download_name=f"车站设施数据汇总_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")


# ==================== API路由 ====================
@app.route('/api/get_tree_data')
def get_tree_data():
    """获取树形结构数据"""
    return jsonify(railway_data)


@app.route('/api/get_station_data')
def get_station_data():
    """获取当前选中车站的数据"""
    railway = request.args.get('railway', '国铁集团')
    bureau = request.args.get('bureau', '北京局')
    section = request.args.get('section', '北京车务段')
    station = request.args.get('station', '北京南站')

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        return jsonify(station_data)
    return jsonify({"status": "error"}), 404


@app.route('/api/add_open_area', methods=['POST'])
def add_open_area():
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_key = f"{railway}_{bureau}_{section}_{station}"
        init_counters_for_station(station_key)
        new_item = data.get('item', {})
        new_item['id'] = id_counters[station_key]['open_areas']
        id_counters[station_key]['open_areas'] += 1
        station_data['open_areas'].append(new_item)
        return jsonify({"status": "success", "id": new_item['id']})
    return jsonify({"status": "error"}), 404


@app.route('/api/update_open_area/<int:item_id>', methods=['PUT'])
def update_open_area(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        for i, item in enumerate(station_data['open_areas']):
            if item['id'] == item_id:
                data['id'] = item_id
                station_data['open_areas'][i] = data
                return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route('/api/delete_open_area/<int:item_id>', methods=['DELETE'])
def delete_open_area(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_data['open_areas'] = [item for item in station_data['open_areas'] if item['id'] != item_id]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


# 大型休息厅API
@app.route('/api/add_large_hall', methods=['POST'])
def add_large_hall():
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_key = f"{railway}_{bureau}_{section}_{station}"
        init_counters_for_station(station_key)
        new_item = data.get('item', {})
        new_item['id'] = id_counters[station_key]['large_halls']
        id_counters[station_key]['large_halls'] += 1
        station_data['large_halls'].append(new_item)
        return jsonify({"status": "success", "id": new_item['id']})
    return jsonify({"status": "error"}), 404


@app.route('/api/update_large_hall/<int:item_id>', methods=['PUT'])
def update_large_hall(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        for i, item in enumerate(station_data['large_halls']):
            if item['id'] == item_id:
                data['id'] = item_id
                station_data['large_halls'][i] = data
                return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route('/api/delete_large_hall/<int:item_id>', methods=['DELETE'])
def delete_large_hall(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_data['large_halls'] = [item for item in station_data['large_halls'] if item['id'] != item_id]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


# 中型休息厅API
@app.route('/api/add_medium_hall', methods=['POST'])
def add_medium_hall():
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_key = f"{railway}_{bureau}_{section}_{station}"
        init_counters_for_station(station_key)
        new_item = data.get('item', {})
        new_item['id'] = id_counters[station_key]['medium_halls']
        id_counters[station_key]['medium_halls'] += 1
        station_data['medium_halls'].append(new_item)
        return jsonify({"status": "success", "id": new_item['id']})
    return jsonify({"status": "error"}), 404


@app.route('/api/update_medium_hall/<int:item_id>', methods=['PUT'])
def update_medium_hall(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        for i, item in enumerate(station_data['medium_halls']):
            if item['id'] == item_id:
                data['id'] = item_id
                station_data['medium_halls'][i] = data
                return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route('/api/delete_medium_hall/<int:item_id>', methods=['DELETE'])
def delete_medium_hall(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_data['medium_halls'] = [item for item in station_data['medium_halls'] if item['id'] != item_id]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


# 小型休息厅API
@app.route('/api/add_small_hall', methods=['POST'])
def add_small_hall():
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_key = f"{railway}_{bureau}_{section}_{station}"
        init_counters_for_station(station_key)
        new_item = data.get('item', {})
        new_item['id'] = id_counters[station_key]['small_halls']
        id_counters[station_key]['small_halls'] += 1
        station_data['small_halls'].append(new_item)
        return jsonify({"status": "success", "id": new_item['id']})
    return jsonify({"status": "error"}), 404


@app.route('/api/update_small_hall/<int:item_id>', methods=['PUT'])
def update_small_hall(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        for i, item in enumerate(station_data['small_halls']):
            if item['id'] == item_id:
                data['id'] = item_id
                station_data['small_halls'][i] = data
                return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route('/api/delete_small_hall/<int:item_id>', methods=['DELETE'])
def delete_small_hall(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_data['small_halls'] = [item for item in station_data['small_halls'] if item['id'] != item_id]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


# 会议室API
@app.route('/api/add_meeting_room', methods=['POST'])
def add_meeting_room():
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_key = f"{railway}_{bureau}_{section}_{station}"
        init_counters_for_station(station_key)
        new_item = data.get('item', {})
        new_item['id'] = id_counters[station_key]['meeting_rooms']
        id_counters[station_key]['meeting_rooms'] += 1
        station_data['meeting_rooms'].append(new_item)
        return jsonify({"status": "success", "id": new_item['id']})
    return jsonify({"status": "error"}), 404


@app.route('/api/update_meeting_room/<int:item_id>', methods=['PUT'])
def update_meeting_room(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        for i, item in enumerate(station_data['meeting_rooms']):
            if item['id'] == item_id:
                data['id'] = item_id
                station_data['meeting_rooms'][i] = data
                return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route('/api/delete_meeting_room/<int:item_id>', methods=['DELETE'])
def delete_meeting_room(item_id):
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_data['meeting_rooms'] = [item for item in station_data['meeting_rooms'] if item['id'] != item_id]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route('/api/update_basic', methods=['POST'])
def update_basic():
    data = request.json
    railway = data.get('railway', current_path['railway'])
    bureau = data.get('bureau', current_path['bureau'])
    section = data.get('section', current_path['section'])
    station = data.get('station', current_path['station'])

    station_data = get_station_by_path(railway, bureau, section, station)
    if station_data:
        station_data['basic_info'] = data.get('basic_info', {})
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404


@app.route('/api/get_current_path', methods=['GET'])
def get_current_path():
    return jsonify(current_path)


@app.route('/api/set_current_path', methods=['POST'])
def set_current_path():
    data = request.json
    global current_path
    current_path = data
    return jsonify({"status": "success"})


# ==================== 路由 ====================
@app.route('/')
def main_page():
    init_sample_data()
    return render_template('main.html')


@app.route('/edit')
def edit_page():
    init_sample_data()
    return render_template('edit.html')


@app.route('/statistics')
def statistics_page():
    """统计页面"""
    init_sample_data()
    return render_template('statistics.html')



if __name__ == '__main__':
    os.makedirs('templates', exist_ok=True)
    os.makedirs('static/uploads', exist_ok=True)
    app.run(debug=True, port=5000)