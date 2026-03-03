from flask import Flask, render_template, request, redirect, url_for, session, flash
from datetime import datetime
from models.database import db, User, Admin, ParkingLot, ParkingSpot, Reservation

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'garvit123'

db.init_app(app)

def create_database():
    with app.app_context():
        db.create_all()
        print("Database and tables created successfully!")

# -------------------- LOGIN & REGISTER -----------------------

@app.route("/login", methods=['GET', 'POST'])
@app.route("/", methods=['GET', 'POST'])
def login_page():
    if request.method == 'POST':
        username = request.form.get("username")
        password = request.form.get("password")

        if not username or not password:
            flash('Please fill out both fields.', 'warning')
            return redirect(url_for('login_page'))

        user = User.query.filter_by(username=username, password=password).first()

        if user:
            session['username'] = username
            flash(f'Login successful! Welcome to the User Dashboard, {username}!', 'success')
            return redirect(url_for('user_page'))
        elif username == 'admin' and password == 'admin123':
            session['username'] = username
            return redirect(url_for('admin_page'))
        else:
            flash('Invalid username or password.', 'danger')
            return redirect(url_for('login_page'))
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Username already exists!', 'danger')
            return redirect(url_for('register'))
        new_user = User(username=username, password=password)
        db.session.add(new_user)
        db.session.commit()
        flash('Registration successful!', 'success')
        return redirect(url_for('login_page'))
    return render_template('register.html')

# -------------------- USER ROUTES -----------------------

@app.route("/user")
def user_page():
    if 'username' in session:
        username = session['username']
        user = User.query.filter_by(username=username).first()

        # Fetch all parking lots and their occupancy
        lots = ParkingLot.query.all()
        for lot in lots:
            lot.occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()

        # Fetch user's reservations (parking history)
        reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.parking_timestamp.desc()).all()

        parking_history = []
        for res in reservations:
            spot = ParkingSpot.query.get(res.spot_id)
            if spot:
                lot = ParkingLot.query.get(spot.lot_id)
                parking_history.append({
                    'id': res.id,
                    'location': lot.prime_location_name if lot else "Unknown",
                    'vehicle_no': res.vehicle_no,
                    'timestamp': res.parking_timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                    'status': res.status,  # 'O' for occupied, 'A' for available
                    'spot_id': spot.id
                })

        return render_template('user.html', username=username, lots=lots, parking_history=parking_history)

    flash("Please login first.", "warning")
    return redirect(url_for('login_page'))

@app.route('/user/book_spot/<int:lot_id>', methods=['GET', 'POST'])
def book_spot(lot_id):
    if 'username' not in session:
        flash("Please login to book a spot.", "warning")
        return redirect(url_for('login_page'))

    user = User.query.filter_by(username=session['username']).first()
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()

    if not spot:
        flash("No available spots in this lot!", "danger")
        return redirect(url_for('user_page'))

    if request.method == 'POST':
        vehicle_no = request.form.get('vehicle_no')
        spot.status = 'O'

        new_reservation = Reservation(
            spot_id=spot.id,
            user_id=user.id,
            vehicle_no=vehicle_no,
            parking_timestamp=datetime.now(),
            parking_cost=0,  # Will calculate at release time
            status='O'
        )
        spot.status = 'O'
        db.session.add(new_reservation)
        db.session.commit()


        flash("Spot booked successfully!", "success")
        return redirect(url_for('user_page'))

    return render_template('book_spot.html', lot_id=lot_id, spot_id=spot.id, user_id=user.id, username=session['username'])


@app.route('/user/user_search', methods=['POST'])
def user_search():
    if 'username' not in session:
        flash("Please login to search parking lots.", "warning")
        return redirect(url_for('login_page'))

    search_query = request.form.get('search_query')
    lots = []

    if search_query:
        lots = ParkingLot.query.filter(
            (ParkingLot.prime_location_name.ilike(f"%{search_query}%")) |
            (ParkingLot.address.ilike(f"%{search_query}%")) |
            (ParkingLot.pin_code.ilike(f"%{search_query}%"))
        ).all()

    for lot in lots:
        lot.occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()

    return render_template("user.html", username=session['username'], lots=lots)


@app.route("/user/summary_user")
def user_summary():
    if 'username' not in session:
        flash("Login required!", "danger")
        return redirect(url_for('login_page'))
    
    lots = ParkingLot.query.all()
    revenue_data = []
    occupancy_data = []

    for lot in lots:
        occupied = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        available = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        total_revenue = occupied * lot.price

        revenue_data.append({"lot": lot.prime_location_name, "revenue": total_revenue})
        occupancy_data.append({
            "lot": lot.prime_location_name,
            "available": available,
            "occupied": occupied
        })

    return render_template("summary_user.html", revenue_data=revenue_data, occupancy_data=occupancy_data)


@app.route('/editprofile', methods=['GET', 'POST'])
def edit_profile():
    if 'username' not in session:
        flash("Please login to edit your profile.", "warning")
        return redirect(url_for('login_page'))
    user = User.query.filter_by(username=session['username']).first()
    if request.method == 'POST':
        user.username = request.form['username']
        user.password = request.form['password']
        db.session.commit()
        session['username'] = user.username
        flash("Profile updated successfully!", "success")
        return redirect(url_for('user_page'))
    return render_template('edit_profile.html', user=user)

@app.route('/user/release_spot/<int:spot_id>', methods=['GET', 'POST'])
def release_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    reservation = Reservation.query.filter_by(spot_id=spot.id).order_by(Reservation.parking_timestamp.desc()).first()

    if not reservation:
        flash('No reservation found.', 'danger')
        return redirect(url_for('user_page'))

    if request.method == 'POST':
        if spot.status == 'O':
            spot.status = 'A'
            reservation.status = 'A'
            reservation.leaving_timestamp = datetime.utcnow()

            # Calculate and save cost
            time_diff = (datetime.utcnow() - reservation.parking_timestamp).total_seconds() / 3600
            lot = ParkingLot.query.get(spot.lot_id)
            total_cost = round(time_diff * lot.price, 2)
            reservation.parking_cost = total_cost
            db.session.commit()
            flash('Spot released successfully.', 'success')
        else:
            flash('This spot is already available.', 'info')
        return redirect(url_for('user_page'))

    # GET: show release confirmation
    parking_time = reservation.parking_timestamp.strftime('%Y-%m-%d %H:%M:%S')
    releasing_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    time_diff = (datetime.utcnow() - reservation.parking_timestamp).total_seconds() / 3600
    lot = ParkingLot.query.get(spot.lot_id)
    total_cost = round(time_diff * lot.price, 2)

    return render_template('release_spot.html',
                           spot_id=spot.id,
                           vehicle_no=reservation.vehicle_no,
                           parking_time=parking_time,
                           releasing_time=releasing_time,
                           total_cost=total_cost)


# -------------------- ADMIN ROUTES -----------------------

@app.route("/admin")
def admin_page():
    username = session.get('username')
    lots = ParkingLot.query.all()
    for lot in lots:
        lot.occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
    return render_template('admin.html', lots=lots)

@app.route('/admin/admin_parkinglots')
def admin_parkinglots():
    lots = ParkingLot.query.all()
    for lot in lots:
        lot.occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
    return render_template('admin_parkinglots.html', lots=lots)

@app.route('/admin/admin_editprofile', methods=['GET', 'POST'])
def admin_edit_profile():
    if 'username' not in session:
        flash("Please login to edit your profile.", "warning")
        return redirect(url_for('login_page'))
    user = User.query.filter_by(username=session['username']).first()
    if request.method == 'POST':
        user.username = request.form['username']
        user.password = request.form['password']
        db.session.commit()
        session['username'] = user.username
        flash("Profile updated successfully!", "success")
        return redirect(url_for('admin_page'))
    return render_template('admin_editprofile.html', user=user)

@app.route('/admin/add_lot', methods=['GET', 'POST'])
def add_parking_lot():
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        address = request.form['address']
        pin_code = request.form['pin']
        max_spots = int(request.form['max_spots'])
        lot = ParkingLot(prime_location_name=name, price=price, address=address, pin_code=pin_code, maximum_number_of_spots=max_spots)
        db.session.add(lot)
        db.session.flush()
        for i in range(1, max_spots + 1):
            spot = ParkingSpot(lot_id=lot.id, status='A', spot_number=f"Spot-{i}")
            db.session.add(spot)
        db.session.commit()
        flash("Parking Lot Added with Spots!", "success")
        return redirect(url_for('admin_parkinglots'))
    return render_template('add_lot.html')

@app.route('/admin/deletelot/<int:lot_id>')
def delete_parking_lot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    ParkingSpot.query.filter_by(lot_id=lot.id).delete()
    db.session.delete(lot)
    db.session.commit()
    flash("Parking Lot and its Spots Deleted!", "danger")
    return redirect(url_for('admin_parkinglots'))

@app.route('/admin/lot_details/<int:lot_id>')
def lot_details(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    return render_template('lot_details.html', lot=lot, spots=spots)

@app.route('/admin/user_details/<int:user_id>')
def admin_user_details(user_id):
    user = User.query.get_or_404(user_id)
    reservations = Reservation.query.filter_by(user_id=user.id).all()
    return render_template('admin_user_details.html', user=user, reservations=reservations)


@app.route('/admin/admin_users')
def admin_users():
    users = User.query.all()  # Get all users
    return render_template('admin_users.html', users=users)



# Delete User
@app.route('/admin/delete_user/<int:user_id>', methods=['POST'])
def admin_delete_user(user_id):
    user = User.query.get_or_404(user_id)
    reservations = Reservation.query.filter_by(user_id=user.id).all()
    for res in reservations:
        spot = ParkingSpot.query.get(res.spot_id)
        if spot:
            spot.status = 'A'  # Mark spot as Available
        db.session.delete(res)
    db.session.delete(user)
    db.session.commit()
    flash('User deleted successfully.', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/spot_details/<int:spot_id>')
def spot_details(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    return render_template('spot_details.html', spot=spot)

@app.route('/admin/delete_spot/<int:spot_id>', methods=['POST'])
def delete_spot(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    lot = ParkingLot.query.get(spot.lot_id)
    if spot.status == 'A':
        db.session.delete(spot)
        db.session.commit()
        occupied_count = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        lot.occupied_spots = occupied_count
        db.session.commit()
        flash("Spot Deleted!", "success")
    else:
        flash("Cannot delete an Occupied Spot!", "danger")
    return redirect(url_for('lot_details', lot_id=spot.lot_id))

@app.route('/admin/occupied_spot_details/<int:spot_id>')
def occupied_spot_details(spot_id):
    spot = ParkingSpot.query.get_or_404(spot_id)
    reservation = Reservation.query.filter_by(spot_id=spot.id).first()

    estimated_cost = "N/A"
    if reservation:
        lot = ParkingLot.query.get(spot.lot_id)
        if reservation.parking_timestamp:
            time_diff = (datetime.utcnow() - reservation.parking_timestamp).total_seconds() / 3600
            estimated_cost = round(time_diff * lot.price, 2)

    return render_template('occupied_spot_details.html', spot=spot, reservation=reservation, estimated_cost=estimated_cost)


@app.route('/search', methods=['GET'])
def search():
    filter_by = request.args.get('filter_by')
    query = request.args.get('query')
    lots = []

    if filter_by == 'user_id':
        try:
            user_id = int(query)
            user = User.query.filter_by(id=user_id).first()
        except (ValueError, TypeError):
            user = None
        if user:
            reservations = Reservation.query.filter_by(user_id=user.id).all()
            lot_ids = list(set([ParkingSpot.query.get(res.spot_id).lot_id for res in reservations]))
            lots = ParkingLot.query.filter(ParkingLot.id.in_(lot_ids)).all()
    if filter_by == 'location':
        lots = ParkingLot.query.filter(ParkingLot.prime_location_name.ilike(f'%{query}%')).all()

    for lot in lots:
        lot.occupied_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        lot.spots = ParkingSpot.query.filter_by(lot_id=lot.id).all()

    return render_template('search.html', lots=lots)

@app.route('/admin/editlot/<int:lot_id>', methods=['GET', 'POST'])
def editlot(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    if request.method == 'POST':
        lot.prime_location_name = request.form['prime_location_name']  # use correct key
        lot.address = request.form['address']  # make sure this matches HTML
        lot.pin_code = request.form['pin_code']  # ensure this too
        lot.maximum_number_of_spots = int(request.form['maximum_number_of_spots'])
        db.session.commit()
        flash('Parking Lot updated successfully!', 'success')
        return redirect(url_for('admin_parkinglots'))
    return render_template('editlot.html', lot=lot)


@app.route('/admin/summary')
def summary():
    lots = ParkingLot.query.all()
    lot_names = [lot.prime_location_name for lot in lots]
    revenues = [lot.price * ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count() for lot in lots]

    total_available = ParkingSpot.query.filter_by(status='A').count()
    total_occupied = ParkingSpot.query.filter_by(status='O').count()

    return render_template('summary.html', 
                           lot_names=lot_names, 
                           revenues=revenues, 
                           total_available=total_available, 
                           total_occupied=total_occupied)


# -------------------- MAIN -----------------------

if __name__ == "__main__":
    create_database()
    app.run(debug=True, port=5054)