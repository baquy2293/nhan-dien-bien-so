
# _______________________________Thêm thư viện___________________________________________________________

from flask import Flask, render_template, Response, request, redirect, flash
import cv2
from flask_login.utils import login_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin
from sqlalchemy.sql import func
from ultralytics import YOLO
import numpy as np
import easyocr
import requests
from datetime import datetime
import pytz
import re
from flask_caching import Cache
from flask_lazyviews import LazyViews
import array as arr 
import logging
from io import StringIO
import csv
from flask import make_response
from sqlalchemy import LargeBinary
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from sqlalchemy import extract
# _______________________________Khai báo__________________________________________________________________

app = Flask(__name__,static_folder='static')               
app.config['SECRET_KEY'] = '8sfkahf0-qdqb82hd'
login = LoginManager(app=app)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///license.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
user = None
cache = Cache(app, config={'CACHE_TYPE': 'simple'})
lazyviews = LazyViews(app)

# Khởi tạo scheduler
scheduler = BackgroundScheduler()

class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(50), nullable=False)
    license_phate = db.Column(db.String(50), nullable=False)
    department = db.Column(db.String(50))  # Thêm cột department

    def __init__(self, name, license_phate, department):  # Cập nhật hàm khởi tạo
        self.name = name
        self.license_phate = license_phate
        self.department = department
class Admin(db.Model):
    __tablename__ = "admin"
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    username = db.Column(db.String(50), nullable=False)
    password = db.Column(db.String(50), nullable=False)

    def __init__(self, username, password):
        self.username = username
        self.password = password
    def is_active(self):
        return True
    def get_id(self):
        return str(self.id)

class Manager(db.Model):
    __tablename__="manager"
    id = db.Column(db.Integer, primary_key = True, autoincrement=True)
    license_phate = db.Column(db.String(50), nullable=False)
    checkin=db.Column(db.DateTime, nullable=True)
    checkout=db.Column(db.DateTime, nullable=True)
    license_plate_image_in = db.Column(LargeBinary)
    license_plate_image_out = db.Column(LargeBinary)
    def __init__(self, license_phate, checkin=None, checkout=None, license_plate_image_in=None, license_plate_image_out=None):
        self.license_phate = license_phate
        self.checkin = checkin
        self.checkout = checkout
        self.license_plate_image_in = license_plate_image_in
        self.license_plate_image_out = license_plate_image_out
        
class Statistics(db.Model):
    __tablename__ = "statistics"
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    license_plate = db.Column(db.String(50), nullable=False)
    current_date = db.Column(db.Date, nullable=False)
    checkin_time = db.Column(db.String(8), nullable=True)  # Store time as string in HH:MM:SS format
    checkout_time = db.Column(db.String(8), nullable=True)

    def __init__(self, license_plate, current_date, checkin=None, checkout=None):
        self.license_plate = license_plate
        self.current_date = current_date
        self.checkin_time = checkin
        self.checkout_time = checkout

with app.app_context():
    db.create_all()
# ______________________________API_______________________________________________________________________


model = YOLO('best.pt')
#Login
@login.user_loader
def user_load(user_id):
    return Admin.query.get(user_id)

@app.route('/login', methods=["POST"])
def login():
    global admin
    username = request.form.get("username")
    password = str(request.form.get("password"))
    remember_me = request.form.get('remember-me') 

    if remember_me:
        session['username'] = username
    user = Admin.query.filter_by(username=username, password=password).first()
    if user:
        login_user(user)
        return redirect("api/video")
    else:
        flash('Sai tài khoản hoặc mật khẩu. Vui lòng đăng nhập lại', 'danger')
        return redirect("/")

@app.route('/logout')
def logout():
    logout_user()
    return redirect("/")

@app.route('/admin')
def admin():
    global user
    users = User.query.all()
    return render_template('user.html', users = users)

@app.route('/statisticals', methods=['GET', 'POST'])
def statisticals():
    combined_data = []

    if request.method == 'POST':
        data = request.get_json()
        selected_date_str = data.get('selected_date')
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        print(selected_date_str)  # Debug: in ra ngày được chọn

        # Truy vấn dữ liệu từ cơ sở dữ liệu
        users = User.query.all()
        statistics = Statistics.query.filter(Statistics.current_date == selected_date).all()  # Lọc dữ liệu theo ngày được chọn

        print(statistics)  # Debug: in ra dữ liệu truy vấn từ statistics

        # Kết hợp dữ liệu từ hai bảng
        for stat in statistics:
            user = next((u for u in users if u.license_phate == stat.license_plate), None)
            if user:
                print(user)
                combined_data.append({'user': user, 'statistics': stat})
                print(combined_data)
    return render_template('statistical.html', combined_data=combined_data)

@app.route('/monthly', methods=['GET', 'POST'])
def monthly():
    return render_template('monthly_statistics.html')

@app.route('/monthly_statistics', methods=['POST'])
def monthly_statistics():
    if request.method == 'POST':
        data = request.get_json()
        selected_month_str = data.get('selected_month')
        selected_month = int(selected_month_str)
        print(selected_month_str)  # Debug: Print the selected month

        # Query data from the database
        users = User.query.all()
        statistics = Statistics.query.filter(extract('month', Statistics.current_date) == selected_month).all()

        print(statistics)  # Debug: Print the queried statistics

        combined_data = []

        # Combine data from users and statistics
        for stat in statistics:
            user = next((u for u in users if u.license_phate == stat.license_plate), None)
            if user:
                combined_data.append({
                    'date': stat.current_date.strftime('%Y-%m-%d'),  # Convert to string
                    'username': user.name,
                    'license_plate': user.license_phate,
                    'checkin_time': str(stat.checkin_time),  # Convert to string
                    'checkout_time': str(stat.checkout_time)  # Convert to string
                })

        return jsonify(combined_data)
    
@app.route('/monthly_day', methods=['POST'])
def monthly_day():
    selected_month = request.json.get('selected_month')  # Lấy tháng được chọn từ yêu cầu POST

    # Tính ngày đầu tiên và cuối cùng của tháng được chọn
    first_day = datetime(year=datetime.now().year, month=selected_month, day=1).date()
    if selected_month == 12:
        last_day = datetime(year=datetime.now().year+1, month=1, day=1).date()
    else:
        last_day = datetime(year=datetime.now().year, month=selected_month+1, day=1).date()

    # Truy vấn cơ sở dữ liệu để lấy dữ liệu thống kê theo tháng
    monthly_statistics = db.session.query(User, db.func.count(Statistics.id)) \
                                    .outerjoin(Statistics, User.license_phate == Statistics.license_plate) \
                                    .filter(Statistics.current_date >= first_day) \
                                    .filter(Statistics.current_date < last_day) \
                                    .group_by(User.id) \
                                    .all()

    # Tạo một từ điển để lưu trữ số ngày làm việc của từng user
    days_worked_dict = {user.id: days_worked for user, days_worked in monthly_statistics}

    # Truy vấn tất cả các user
    all_users = User.query.all()

    # Format dữ liệu trả về
    data = []
    for user in all_users:
        days_worked = days_worked_dict.get(user.id, 0)  # Lấy số ngày làm việc, nếu không tồn tại thì trả về 0
        data.append({
            'user': {
                'id': user.id,
                'name': user.name,
                'license_plate': user.license_phate,
                'department': user.department
            },
            'monthly_statistics': days_worked,
            'selected_month': selected_month
        })

    return jsonify(data)

@app.route('/monthly_lincese', methods=['POST'])
def monthly_lincese():
    data = request.json
    license_plate = data.get('license_plate')
    selected_month = data.get('selected_month')
    print(license_plate)
    print(selected_month)
    users = User.query.all()
    statistics = Statistics.query.filter(
    extract('month', Statistics.current_date) == selected_month,
    Statistics.license_plate == license_plate
    ).all()

    print(statistics)  # Debug: Print the queried statistics

    combined_data = []

        # Combine data from users and statistics
    for stat in statistics:
        user = next((u for u in users if u.license_phate == license_plate), None)
        if user:
            combined_data.append({
            'date': stat.current_date.strftime('%Y-%m-%d'),  # Convert to string
            'username': user.name,
            'license_plate': user.license_phate,
            'checkin_time': str(stat.checkin_time),  # Convert to string
            'checkout_time': str(stat.checkout_time)  # Convert to string
            })

    return jsonify(combined_data)

@app.route('/deleteuser/<int:id>')
def deleteuser(id):
    global user
    User.query.filter_by(id=id).delete()
    db.session.commit()
    users = User.query.all()
    return render_template('user.html', users = users)

@app.route('/register', methods=["POST"])
def register():
    name = request.form.get("username")
    license_phate = request.form.get("license-plates")
    department = request.form.get("department")
    re = User(name=name, license_phate=license_phate, department=department)
    db.session.add(re)
    db.session.commit()
    users = User.query.all()
    return render_template('user.html', users=users)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/open', methods=['POST'])
def open_servo():
    print("Open servo")
    return {'status': 'success'}

@app.route('/close', methods=['POST'])
def close_servo():
    print("Close servo")
    return {'status': 'success'}

def get_total_obstacles():
    total_obstacles = 0
    for pi_id in sensor_data:
        
        for sensor_id in sensor_data[pi_id]:
            print(pi_id)
            print(sensor_id)
            print(sensor_data[pi_id][sensor_id])
            print("______________________________________")
            if sensor_data[pi_id][sensor_id] is None or sensor_data[pi_id][sensor_id] == 1:
                total_obstacles += 1
    # print(total_obstacles)
    # print("************************")
    return total_obstacles

def fetch_and_process_image(url, auth, model, source):
    response = requests.get(url, auth=auth)
    img_array = np.array(bytearray(response.content), dtype=np.uint8)
    image = cv2.imdecode(img_array, -1)
    filtered_string = process_image(model, image, source)
    return filtered_string

def process_db_operations(filtered_string, in_or_out):
    user = User.query.filter_by(license_phate=filtered_string).first()
    if user:
        tz_VN = pytz.timezone('Asia/Ho_Chi_Minh')
        datetime_VN = datetime.now(tz_VN)
        current_date = datetime_VN.date()
        current_time = datetime_VN.strftime('%Hh%Mm%Ss')

        if in_or_out == 'in':
            result = Manager.query.filter(
                Manager.license_phate == filtered_string,
                (Manager.checkin.is_(None) | Manager.checkout.is_(None))
            ).first()
            if result is None:
                with open("static/cropped_image_in.jpg", 'rb') as f:
                    image_data = f.read()
                new_record = Manager(
                    license_phate=filtered_string, 
                    checkin=datetime_VN, 
                    license_plate_image_in=image_data
                )
                db.session.add(new_record)

            stat_record = Statistics.query.filter_by(
                license_plate=filtered_string, 
                current_date=current_date
            ).first()
            if stat_record is None:
                new_stat_record = Statistics(
                    license_plate=filtered_string, 
                    current_date=current_date, 
                    checkin=current_time
                )
                db.session.add(new_stat_record)

        elif in_or_out == 'out':
            print("----------------------------------------------------------------------")
            result = Manager.query.filter(
                Manager.license_phate == filtered_string,
                (Manager.checkout.is_(None))
            ).first()
            if result is not None:
               
                with open("static/cropped_image_out.jpg", 'rb') as f:
                    image_data = f.read()
                result.checkout = datetime_VN
                result.license_plate_image_out = image_data

            stat_record = Statistics.query.filter_by(
                license_plate=filtered_string, 
                current_date=current_date
            ).first()
            if stat_record is None:
                new_stat_record = Statistics(
                    license_plate=filtered_string, 
                    current_date=current_date, 
                    checkin=current_time
                )
                db.session.add(new_stat_record)
            else:
                stat_record.checkout_time = current_time

            db.session.commit()
            return user.id, user.name, user.department

        db.session.commit()
    return "", "", ""

license_plate_string = None
license_plate_string_out = None

@app.route('/api/video/in', methods=['GET'])
def video_in():
    global license_plate_string
    img_url_in = "http://ras:8080/?action=snapshot.jpg"
    try:
        filtered_string_in = fetch_and_process_image(img_url_in, ('ras', '1'), model, 'ras')
    except Exception as exc:
        print(f"in generated an exception: {exc}")
        filtered_string_in = None

    if filtered_string_in:
        license_plate_string = filtered_string_in
        print("Debug: license_plate_string set to", license_plate_string)
        process_db_operations(filtered_string_in, 'in')
    
    return jsonify({"status": "success", "data": filtered_string_in})

@app.route('/api/send_text_in', methods=['POST'])
def send_text_in():
    global license_plate_string
    if license_plate_string:
        user = User.query.filter_by(license_phate=license_plate_string).first()
        if user:
            print("Debug: Entering send_text_in route")
            print(license_plate_string)
            return jsonify({"status": "success"})
        else:
            return jsonify({"status": "failure_nodata", "error": "License plate not found. Confirm to proceed."})
    else:
        print("Debug: license_plate_string is not set")
        return jsonify({"status": "failure", "error": "No license plate string available"}), 400
    

@app.route('/api/confirm_send_text_in', methods=['POST'])
def confirm_send_text_in():
    global license_plate_string
    print("Debug: Entering confirm_send_text_in route")
    if license_plate_string:
        send_text_and_signal_to_raspi(license_plate_string)
        print("Debug: license_plate_string sent to raspi", license_plate_string)
        return jsonify({"status": "success"})
    else:
        return jsonify({"status": "failure", "error": "No license plate string available"}), 400
    

@app.route('/api/video/out', methods=['GET'])
def video_out():
    global license_plate_string_out
    img_url_out = "http://pi:8080/?action=snapshot.jpg"
    with open("static/cropped_image_out.jpg", 'rb') as f:
        image_data = f.read()
    try:
        
        filtered_string_out = fetch_and_process_image(img_url_out, ('pi', '1'), model, 'pi')
    except Exception as exc:
        print(f"out generated an exception: {exc}")
        filtered_string_out = None
    id = ""
    name = ""
    department = ""

    if filtered_string_out:
        license_plate_string_out = filtered_string_out
        
        id, name, department = process_db_operations(filtered_string_out, 'out')

    return jsonify({"status": "success", "data": filtered_string_out, "id": id, "name": name, "department": department})

@app.route('/api/send_text_out', methods=['POST'])
def send_text_out():
    global license_plate_string_out
    if license_plate_string_out:
        send_text_and_signal_to_raspi1(license_plate_string_out)
        return jsonify({"status": "success"})
    else:
        print("Debug: license_plate_string is not set")
        return jsonify({"status": "failure", "error": "No license plate string available"}), 400

@app.route('/api/video', methods=['GET', 'POST'])
def video():
    img_url_in = "http://ras:8080/?action=snapshot.jpg"
    try:
       filtered_string_in = fetch_and_process_image(img_url_in, ('ras', '1'), model, 'ras')
 
    except Exception as exc:
        print(f"in generated an exception: {exc}")
        filtered_string_in = None
        
    return render_template('test.html', filtered_string_in = filtered_string_in)

def process_image(model, image, source):
    mytext = ""
    results = model(image)
    boxes = results[0].boxes
    image_model = YOLO('best1.pt')

    if boxes.shape[0] > 0:
        x_min = int(boxes.xyxy[0][0])
        y_min = int(boxes.xyxy[0][1])
        x_max = int(boxes.xyxy[0][2])
        y_max = int(boxes.xyxy[0][3])
        cropped_image = image[y_min:y_max, x_min:x_max]
        results  = image_model.predict(cropped_image)
        if source == 'pi':
            cv2.imwrite("static/cropped_image_out.jpg", cropped_image)
        elif source == 'ras':
            cv2.imwrite("static/cropped_image_in.jpg", cropped_image)
            
        gray_image = cv2.cvtColor(cropped_image, cv2.COLOR_BGR2GRAY)
        image_results = image_model(cropped_image) 
        print(image_results)
        # Extract bounding boxes, classes, names, and confidences
        
        boxes = results[0].boxes.xyxy.tolist()
        classes = results[0].boxes.cls.tolist()
        names = results[0].names
        confidences = results[0].boxes.conf.tolist()
        a = []
        for _ in range(15):
            hang = [0] * 3  # Create a row containing 3 elements with value 0
            a.append(hang)

        row = 0 
        for box, cls, conf in zip(boxes, classes, confidences):
            x1, y1, x2, y2 = box
            confidence = conf
            detected_class = cls
            name = names[int(cls)]
            a[row][0] = x1
            a[row][1] = y1
            a[row][2] = detected_class
            row += 1
        for i in range(row):
            print(f"{a[i][0]} x {a[i][1]} x {a[i][2]}")
        print(f"row: {row}")
        line1 = [15]*row
        line2 = [15]*row
        visit = [15]*row
        for i in range(row): 
            line1[i] = 10000
            line2[i] = 10000
            visit[i] = 0
                
        check = 0
        for i in range(row): 
            if(a[i][1]<30):
                if(visit[i] == 0):
                    check = i
                    for j in range(row):
                        if(visit[j] == 0):
                            visit[j] = 1
                            print(f"{a[check][1]} x {a[j][1]}")
                            if(a[j][1] - a[check][1] <= 20):
                                line1.append(j)
                            else:
                                line2.append(j)
            
            
        print(line1)
        print(line2)
        for i in range(len(line1)-1):
            for j in range(i + 1, len(line1)):
                if(line1[i] != 10000):
                    if a[line1[i]][0] > a[line1[j]][0]:
                        tem = line1[i]
                        line1[i] = line1[j]
                        line1[j] = tem
                        
        for i in range(len(line2)-1):
            for j in range(i + 1, len(line2)):
                if(line2[i] != 10000):
                    if a[line2[i]][0] > a[line2[j]][0]:
                        # Swap elements if condition is true
                        tem = line2[i]
                        line2[i] = line2[j]
                        line2[j] = tem
                        
        
        for i in range(len(line1)):
            if(line1[i] != 10000):
                mytext += names[a[line1[i]][2]]
        for i in range(len(line2)):
            if(line2[i] != 10000):
                mytext += names[a[line2[i]][2]]
        print(mytext)
        print(line1)
        print(line2)
    print(mytext)
    return mytext

def send_text_and_signal_to_raspi(license_plate):
    if license_plate:
        send_text_to_raspi(license_plate)

def send_text_to_raspi(filtered_string):
    if filtered_string:
        raspi_ip = 'ras'
        raspi_url = f'http://{raspi_ip}:5001/receive_text'  
        data = {'filtered_string': filtered_string}
        response = requests.post(raspi_url, json=data)
        if response.status_code == 200:
            print('Văn bản đã được gửi đến RasPi thành công')
        else:
            print('Không thể gửi văn bản đến RasPi')

def send_text_and_signal_to_raspi1(license_plate1):
    if license_plate1:
        send_text_to_raspi1(license_plate1)

def send_text_to_raspi1(filtered_string1):
    if filtered_string1:
        raspi_ip = 'pi'
        raspi_url = f'http://{raspi_ip}:5001/receive_text'  
        data = {'filtered_string': filtered_string1}
        response = requests.post(raspi_url, json=data)
        if response.status_code == 200:
            print('Văn bản đã được gửi đến RasPi thành công')
        else:
            print('Không thể gửi văn bản đến RasPi')

@app.route('/videoplayback1')
def videoplayback1():
    data = db.session.query(
        User.id,
        User.name,
        User.license_phate,  # Sửa tên cột license_phate
        User.department,  
        Manager.id,
        func.strftime('%Y-%m-%d %H:%M:%S', Manager.checkout).label('formatted_checkout'),
        func.strftime('%Y-%m-%d %H:%M:%S', Manager.checkin).label('formatted_checkin')
    ).join(Manager, User.license_phate == Manager.license_phate).all()
    # Convert data to list of dictionaries for JSON serialization
    data_dict = [
        {'id': row.id,
         'name': row.name,
         'license_phate': row.license_phate,
         'department': row.department,
         'formatted_checkin': row.formatted_checkin,
         'formatted_checkout': row.formatted_checkout
        } for row in data
    ]
    return jsonify(data_dict)

@app.route('/videoplayback')
def videoplayback():
  
    return render_template('table.html')

@app.route('/updateuser/<int:id_edit>', methods=["POST"])
def updateuser(id_edit):
    # Lấy thông tin được gửi từ yêu cầu POST
    name = request.form.get("name")
    license_phate = request.form.get("licensePlates")
    department = request.form.get("department")

    # Tìm người dùng trong cơ sở dữ liệu dựa trên ID
    user = User.query.get(id_edit)
    if user:
        # Cập nhật thông tin của người dùng
        user.name = name
        user.license_phate = license_phate
        user.department = department

        # Lưu thay đổi vào cơ sở dữ liệu
        db.session.commit()
        # Trả về phản hồi thành công nếu cập nhật thành công
        return 'User updated successfully'
    else:
        # Trả về lỗi nếu không tìm thấy người dùng
        return 'User not found', 404

@app.route('/download/<table>', methods=['GET'])
def download_csv(table):
    try:
        # Ghi log để theo dõi quá trình xử lý yêu cầu tải tệp CSV
        logging.info(f'Request to download CSV for table: {table}')
        
        # Tạo một biến lưu trữ dữ liệu CSV
        csv_data = StringIO()
        csv_writer = csv.writer(csv_data, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Kiểm tra bảng được yêu cầu và truy vấn dữ liệu từ cơ sở dữ liệu
        if table == 'manage':
            data = Manager.query.all()
            # Ghi dữ liệu vào file CSV
            csv_writer.writerow(['ID', 'License Plates', 'Checkin', 'Checkout'])
            for item in data:
                csv_writer.writerow([item.id, item.license_phate, item.checkin, item.checkout])

        elif table == 'user':
            data = User.query.all()
            # Ghi dữ liệu vào file CSV
            csv_writer.writerow(['ID', 'Name', 'License Plates', 'Department'])
            for item in data:
                csv_writer.writerow([item.id, item.name, item.license_phate, item.department])
        elif table == 'in_and_out':
            data = db.session.query(
                Manager.id,
                User.name,
                User.department,
                Manager.license_phate,
                Manager.checkin,
                Manager.checkout,
            ).join(Manager, User.license_phate == Manager.license_phate).all()
            # Ghi dữ liệu vào file CSV
            csv_writer.writerow(['ID', 'Name' , 'Department','License Plates', 'Checkin', 'Checkout'])
            for item in data:
                csv_writer.writerow([item.id,item.name , item.department, item.license_phate, item.checkin, item.checkout])

        # Tạo một đối tượng phản hồi chứa dữ liệu CSV
        response = make_response(csv_data.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={table}.csv'
        response.headers['Content-Type'] = 'text/csv; charset=utf-8-sig'

        return response

    except Exception as e:
        # Ghi log cho bất kỳ ngoại lệ nào xảy ra trong quá trình xử lý yêu cầu
        logging.error(f'An error occurred: {str(e)}')
        
        # Trả về một phản hồi lỗi nếu có lỗi xảy ra
        return 'An error occurred while processing the request.', 500
    
# Biến lưu trữ dữ liệu cảm biến
sensor_data = {
    "ras": {"sensor1ras": None, "sensor2ras": None,"sensor3ras": None,"sensor4ras": None},
    "pi": {"sensor1ras": None, "sensor2ras": None,"sensor3ras": None,"sensor4ras": None},
}

@app.route('/update_sensor', methods=['POST'])
def update_sensor():
    data = request.json
    raspberry_id = data['raspberry_id']
    sensor_id = data['sensor_id']
    value = data['value']
    
    # Cập nhật dữ liệu cảm biến
    sensor_data[raspberry_id][sensor_id] = value
    
    return jsonify({"status": "success", "data": sensor_data})

@app.route('/get_sensor_data', methods=['GET'])
def get_sensor_data():
    total_obstacles = get_total_obstacles()
    return jsonify(total_obstacles)


if __name__ == '__main__':
    
    app.run(host='0.0.0.0',port=5000,debug=True)


