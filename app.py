from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import text, func
import hashlib

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'

# MySQL Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://hrm_user:SecurePass123!@localhost/hrm_system'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

# Models
class Department(db.Model):
    __tablename__ = 'departments'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text)
    manager = db.Column(db.String(100))
    budget = db.Column(db.Float, default=0.00)
    head_count = db.Column(db.Integer, default=0)
    status = db.Column(db.String(20), default='Active')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Changed from Employee to User
    employees = db.relationship('User', backref='department', lazy=True, foreign_keys='User.dept_id')

class Role(db.Model):
    __tablename__ = 'roles'
    role_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(200))
    status = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    users = db.relationship('User', backref='role', lazy=True, foreign_keys='User.role_id')

# NEW User model (replaces Employee)
class User(db.Model):
    __tablename__ = 'users'
    employee_id = db.Column(db.Integer, primary_key=True, autoincrement=False)  # Change this line
    first_name = db.Column(db.String(100), nullable=False)
    # ... rest of the model stays the same ...
    last_name = db.Column(db.String(100))
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    mobile = db.Column(db.String(20))
    dept_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'))
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id', ondelete='SET NULL'))
    reporting_manager_id = db.Column(db.Integer, db.ForeignKey('users.employee_id', ondelete='SET NULL'))
    date_of_joining = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    reporting_manager = db.relationship('User', remote_side=[employee_id], backref='subordinates', foreign_keys=[reporting_manager_id])
    
    # Self-referential relationship for reporting manager
    reporting_manager = db.relationship('User', remote_side=[employee_id], backref='subordinates', foreign_keys=[reporting_manager_id])

    # Add this after your User model and before @app.route('/')
def get_next_employee_id():
    """Get the next available employee ID (reuse deleted IDs)"""
    # Get all existing IDs
    existing_ids = db.session.query(User.employee_id).order_by(User.employee_id).all()
    existing_ids = [id[0] for id in existing_ids]
    
    if not existing_ids:
        return 1
    
    # Find the smallest missing number
    for i in range(1, max(existing_ids) + 2):
        if i not in existing_ids:
            return i
    
    return max(existing_ids) + 1

@app.route('/')
def dashboard():
    try:
        total_departments = Department.query.count()
        total_employees = User.query.count()  # Changed from Employee to User
        total_budget = db.session.query(func.sum(Department.budget)).scalar() or 0
        
        # Get recent employees
        recent_employees = User.query.order_by(User.created_at.desc()).limit(5).all()
        
        recent_employees_data = []
        for emp in recent_employees:
            recent_employees_data.append([
                emp.employee_id,
                emp.first_name,
                emp.last_name or '',
                emp.email,
                emp.department.name if emp.department else 'Not Assigned',
                emp.role.role_name if emp.role else 'Not Assigned',
                emp.date_of_joining.strftime('%d/%m/%Y') if emp.date_of_joining else '—'
            ])
        
        return render_template('dashboard.html',
                             total_departments=total_departments,
                             total_employees=total_employees,
                             recent_employees=recent_employees_data,
                             total_budget=total_budget,
                             present_today=total_employees,
                             active_departments=Department.query.filter_by(status='Active').count())
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return render_template('dashboard.html',
                             total_departments=0,
                             total_employees=0,
                             recent_employees=[],
                             total_budget=0,
                             present_today=0,
                             active_departments=0)

@app.route('/employees')
def employees():
    try:
        all_employees = User.query.order_by(User.employee_id.asc()).all()
        return render_template('employees.html', employees=all_employees, total_employees=len(all_employees))
    except Exception as e:
        flash(f'Error loading employees: {str(e)}', 'danger')
        return render_template('employees.html', employees=[], total_employees=0)
    
@app.route('/employee/add', methods=['GET', 'POST'])
def add_employee():
    departments = Department.query.filter_by(status='Active').all()
    roles = Role.query.filter_by(status=True).all()
    managers = User.query.all()
    
    if request.method == 'POST':
        try:
            email = request.form.get('email')
            username = request.form.get('username') or (email.split('@')[0] if email else 'user')
            
            # Hash password
            password = request.form.get('password')
            hashed_password = hashlib.sha256(password.encode()).hexdigest() if password else hashlib.sha256('default123'.encode()).hexdigest()
            
            # Parse date of joining
            date_of_joining = None
            if request.form.get('date_of_joining'):
                date_of_joining = datetime.strptime(request.form.get('date_of_joining'), '%Y-%m-%d').date()
            
            # *** ADD THIS LINE - Get next available ID ***
            next_id = get_next_employee_id()
            
            employee = User(
                employee_id=next_id,  # *** ADD THIS LINE - Set the ID explicitly ***
                first_name=request.form.get('first_name'),
                last_name=request.form.get('last_name'),
                username=username,
                password=hashed_password,
                email=email,
                mobile=request.form.get('mobile'),
                dept_id=int(request.form.get('dept_id')) if request.form.get('dept_id') and request.form.get('dept_id') != '' else None,
                role_id=int(request.form.get('role_id')) if request.form.get('role_id') and request.form.get('role_id') != '' else None,
                reporting_manager_id=int(request.form.get('reporting_manager_id')) if request.form.get('reporting_manager_id') and request.form.get('reporting_manager_id') != '' else None,
                date_of_joining=date_of_joining
            )
            
            db.session.add(employee)
            db.session.commit()
            flash(f'✅ Employee "{employee.first_name} {employee.last_name or ''}" created successfully with ID #{next_id}!', 'success')
            return redirect(url_for('employees'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error creating employee: {str(e)}', 'danger')
    
    return render_template('add_employee.html', departments=departments, roles=roles, managers=managers)

@app.route('/employee/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    employee = User.query.get_or_404(id)
    departments = Department.query.filter_by(status='Active').all()
    roles = Role.query.filter_by(status=True).all()
    managers = User.query.filter(User.employee_id != id).all()
    
    if request.method == 'POST':
        try:
            employee.first_name = request.form.get('first_name')
            employee.last_name = request.form.get('last_name')
            employee.email = request.form.get('email')
            employee.mobile = request.form.get('mobile')
            
            # Update date of joining
            if request.form.get('date_of_joining'):
                employee.date_of_joining = datetime.strptime(request.form.get('date_of_joining'), '%Y-%m-%d').date()
            
            employee.dept_id = int(request.form.get('dept_id')) if request.form.get('dept_id') and request.form.get('dept_id') != '' else None
            employee.role_id = int(request.form.get('role_id')) if request.form.get('role_id') and request.form.get('role_id') != '' else None
            employee.reporting_manager_id = int(request.form.get('reporting_manager_id')) if request.form.get('reporting_manager_id') and request.form.get('reporting_manager_id') != '' else None
            employee.updated_at = datetime.utcnow()
            
            # Update password if provided
            new_password = request.form.get('password')
            if new_password and new_password.strip():
                employee.password = hashlib.sha256(new_password.encode()).hexdigest()
            
            # Update username
            username = request.form.get('username')
            if username:
                employee.username = username
            
            db.session.commit()
            flash(f'✅ Employee "{employee.first_name} {employee.last_name or ''}" updated successfully!', 'success')
            return redirect(url_for('employees'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error updating employee: {str(e)}', 'danger')
    
    return render_template('edit_employee.html', employee=employee, departments=departments, roles=roles, managers=managers)

@app.route('/employee/delete/<int:id>')
def delete_employee(id):
    employee = User.query.get_or_404(id)
    name = f"{employee.first_name} {employee.last_name or ''}"
    
    try:
        db.session.delete(employee)
        db.session.commit()
        flash(f'✅ Employee "{name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error deleting employee: {str(e)}', 'danger')
    
    return redirect(url_for('employees'))

# Keep all your existing Department routes (unchanged)
@app.route('/departments')
def departments():
    try:
        all_departments = Department.query.order_by(Department.id.asc()).all()
        total_employees = User.query.count()
        return render_template('departments.html', departments=all_departments, total_employees=total_employees)
    except Exception as e:
        flash(f'Error loading departments: {str(e)}', 'danger')
        return render_template('departments.html', departments=[], total_employees=0)

@app.route('/department/add', methods=['GET', 'POST'])
def add_department():
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        manager = request.form.get('manager')
        budget = request.form.get('budget')
        
        if not name:
            flash('Department name is required!', 'danger')
            return redirect(url_for('add_department'))
        
        if Department.query.filter_by(name=name).first():
            flash('Department already exists!', 'danger')
            return redirect(url_for('add_department'))
        
        department = Department(
            name=name, 
            description=description,
            manager=manager,
            budget=float(budget) if budget and budget != '' else 0.00
        )
        
        try:
            db.session.add(department)
            db.session.commit()
            flash(f'✅ Department "{name}" created successfully!', 'success')
            return redirect(url_for('departments'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    
    return render_template('add_department.html')

@app.route('/department/edit/<int:id>', methods=['GET', 'POST'])
def edit_department(id):
    department = Department.query.get_or_404(id)
    if request.method == 'POST':
        department.name = request.form.get('name')
        department.description = request.form.get('description')
        department.status = request.form.get('status')
        department.manager = request.form.get('manager')
        budget_value = request.form.get('budget')
        department.budget = float(budget_value) if budget_value and budget_value != '' else 0.00
        
        try:
            db.session.commit()
            flash(f'✅ Department "{department.name}" updated successfully!', 'success')
            return redirect(url_for('departments'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    
    return render_template('edit_department.html', department=department)

@app.route('/department/delete/<int:id>')
def delete_department(id):
    department = Department.query.get_or_404(id)
    
    if department.employees:
        flash(f'⚠️ Cannot delete "{department.name}" - has {len(department.employees)} employees!', 'danger')
        return redirect(url_for('departments'))
    
    try:
        db.session.delete(department)
        db.session.commit()
        flash(f'✅ Department "{department.name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    
    return redirect(url_for('departments'))

@app.route('/department/view/<int:id>')
def view_department(id):
    department = Department.query.get_or_404(id)
    employees = department.employees
    return render_template('view_department.html', department=department, employees=employees)

# Keep all your existing Role routes (unchanged)
@app.route('/roles')
def roles():
    try:
        all_roles = Role.query.order_by(Role.role_id.asc()).all()
        thirty_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_count = Role.query.filter(Role.created_at >= thirty_days_ago).count()
        return render_template('roles.html', roles=all_roles, recent_count=recent_count)
    except Exception as e:
        flash(f'Error loading roles: {str(e)}', 'danger')
        return render_template('roles.html', roles=[], recent_count=0)

@app.route('/role/create', methods=['POST'])
def create_role():
    role_name = request.form.get('role_name')
    description = request.form.get('description')
    status = request.form.get('status') == '1'
    
    if not role_name:
        flash('Role name is required!', 'danger')
        return redirect(url_for('roles'))
    
    existing_role = Role.query.filter_by(role_name=role_name).first()
    if existing_role:
        flash(f'Role "{role_name}" already exists!', 'danger')
        return redirect(url_for('roles'))
    
    role = Role(role_name=role_name, description=description, status=status)
    
    try:
        db.session.add(role)
        db.session.commit()
        flash(f'✅ Role "{role_name}" created successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error creating role: {str(e)}', 'danger')
    
    return redirect(url_for('roles'))

@app.route('/role/get/<int:role_id>')
def get_role(role_id):
    role = Role.query.get_or_404(role_id)
    return jsonify({
        'role_id': role.role_id,
        'role_name': role.role_name,
        'description': role.description,
        'status': role.status
    })

@app.route('/role/update/<int:role_id>', methods=['POST'])
def update_role(role_id):
    role = Role.query.get_or_404(role_id)
    role_name = request.form.get('role_name')
    description = request.form.get('description')
    status = request.form.get('status') == '1'
    
    if not role_name:
        flash('Role name is required!', 'danger')
        return redirect(url_for('roles'))
    
    existing = Role.query.filter(Role.role_name == role_name, Role.role_id != role_id).first()
    if existing:
        flash(f'Role "{role_name}" already exists!', 'danger')
        return redirect(url_for('roles'))
    
    role.role_name = role_name
    role.description = description
    role.status = status
    
    try:
        db.session.commit()
        flash(f'✅ Role "{role_name}" updated successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error updating role: {str(e)}', 'danger')
    
    return redirect(url_for('roles'))

@app.route('/role/delete/<int:role_id>')
def delete_role(role_id):
    role = Role.query.get_or_404(role_id)
    role_name = role.role_name
    
    try:
        db.session.delete(role)
        db.session.commit()
        flash(f'✅ Role "{role_name}" deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error deleting role: {str(e)}', 'danger')
    
    return redirect(url_for('roles'))

@app.route('/api/department_stats')
def department_stats():
    try:
        departments = Department.query.filter_by(status='Active').order_by(Department.id.asc()).all()
        
        department_names = [dept.name for dept in departments]
        employee_counts = [len(dept.employees) for dept in departments]
        budgets = [dept.budget for dept in departments]
        
        return jsonify({
            'departments': department_names if department_names else ['No Departments'],
            'employee_counts': employee_counts if employee_counts else [0],
            'budgets': budgets if budgets else [0]
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def safe_count(model):
    """Safely get count of records, return 0 if table doesn't exist"""
    try:
        return model.query.count()
    except Exception:
        return 0

if __name__ == '__main__':
    with app.app_context():
        try:
            # Create all tables
            db.create_all()
            
            # Test connection
            db.session.execute(text('SELECT 1'))
            print("\n" + "="*60)
            print("✅ CONNECTED TO MySQL WORKBENCH")
            print("="*60)
            print(f"Database: hrm_system")
            print(f"Departments: {safe_count(Department)}")
            print(f"Roles: {safe_count(Role)}")
            print(f"Employees: {safe_count(User)}")
            print("="*60)
            print("\n🚀 Server running on http://localhost:5000\n")
        except Exception as e:
            print("\n❌ MySQL Connection Failed!")
            print(f"Error: {e}")
            exit(1)
    
    app.run(debug=True, port=5000)