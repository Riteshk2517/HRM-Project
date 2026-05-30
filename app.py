from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import text

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

# Models - Match exactly with your MySQL table columns
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
    
    employees = db.relationship('Employee', backref='department', lazy=True)

class Employee(db.Model):
    __tablename__ = 'employees'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True)
    position = db.Column(db.String(100))
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id', ondelete='SET NULL'))
    phone = db.Column(db.String(20))
    salary = db.Column(db.Float, default=0.00)
    hire_date = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

@app.route('/')
def dashboard():
    try:
        total_departments = Department.query.count()
        total_employees = Employee.query.count()
        active_departments = Department.query.filter_by(status='Active').count()
        
        # Get recent employees for dashboard
        recent_employees = Employee.query.order_by(Employee.hire_date.desc()).limit(5).all()
        recent_employees_data = []
        for emp in recent_employees:
            recent_employees_data.append([
                emp.id,
                emp.name,
                '',
                emp.email,
                emp.department.name if emp.department else 'Not Assigned',
                emp.position or '—',
                emp.hire_date.strftime('%d/%m/%Y') if emp.hire_date else '—'
            ])
        
        # Calculate total budget from all departments
        total_budget = db.session.query(db.func.sum(Department.budget)).scalar() or 0
        
        return render_template('dashboard.html',
                             total_departments=total_departments,
                             total_employees=total_employees,
                             active_departments=active_departments,
                             recent_employees=recent_employees_data,
                             present_today=total_employees,
                             total_budget=total_budget)
    except Exception as e:
        flash(f'Error loading dashboard: {str(e)}', 'danger')
        return render_template('dashboard.html',
                             total_departments=0,
                             total_employees=0,
                             active_departments=0,
                             recent_employees=[],
                             present_today=0,
                             total_budget=0)

@app.route('/departments')
def departments():
    try:
        all_departments = Department.query.order_by(Department.id.asc()).all()
        total_employees = Employee.query.count()
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
            flash(f'✅ Department "{name}" saved to MySQL Workbench successfully!', 'success')
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
            flash(f'✅ Department "{department.name}" updated in MySQL!', 'success')
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
        flash(f'✅ Department "{department.name}" deleted from MySQL!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    
    return redirect(url_for('departments'))

@app.route('/department/view/<int:id>')
def view_department(id):
    department = Department.query.get_or_404(id)
    employees = department.employees
    return render_template('view_department.html', department=department, employees=employees)

@app.route('/employee/add', methods=['GET', 'POST'])
def add_employee():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        position = request.form.get('position')
        department_id = request.form.get('department_id')
        phone = request.form.get('phone')
        salary = request.form.get('salary')
        
        if not name:
            flash('Employee name is required!', 'danger')
            return redirect(url_for('add_employee'))
        
        if email and Employee.query.filter_by(email=email).first():
            flash('Email already exists!', 'danger')
            return redirect(url_for('add_employee'))
        
        employee = Employee(
            name=name,
            email=email,
            position=position,
            department_id=int(department_id) if department_id and department_id != '' else None,
            phone=phone,
            salary=float(salary) if salary and salary != '' else 0.00,
            hire_date=datetime.utcnow()
        )
        
        try:
            db.session.add(employee)
            db.session.commit()
            flash(f'✅ Employee "{name}" saved to MySQL!', 'success')
            return redirect(url_for('employees'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    
    departments = Department.query.filter_by(status='Active').all()
    return render_template('add_employee.html', departments=departments)

@app.route('/employees')
def employees():
    try:
        all_employees = Employee.query.order_by(Employee.id.asc()).all()
        return render_template('employees.html', employees=all_employees, total_employees=len(all_employees))
    except Exception as e:
        flash(f'Error loading employees: {str(e)}', 'danger')
        return render_template('employees.html', employees=[], total_employees=0)

@app.route('/employee/edit/<int:id>', methods=['GET', 'POST'])
def edit_employee(id):
    employee = Employee.query.get_or_404(id)
    if request.method == 'POST':
        employee.name = request.form.get('name')
        employee.email = request.form.get('email')
        employee.position = request.form.get('position')
        employee.department_id = int(request.form.get('department_id')) if request.form.get('department_id') and request.form.get('department_id') != '' else None
        employee.phone = request.form.get('phone')
        salary_value = request.form.get('salary')
        employee.salary = float(salary_value) if salary_value and salary_value != '' else 0.00
        
        try:
            db.session.commit()
            flash(f'✅ Employee "{employee.name}" updated!', 'success')
            return redirect(url_for('employees'))
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error: {str(e)}', 'danger')
    
    departments = Department.query.filter_by(status='Active').all()
    return render_template('edit_employee.html', employee=employee, departments=departments)

@app.route('/employee/delete/<int:id>')
def delete_employee(id):
    employee = Employee.query.get_or_404(id)
    name = employee.name
    
    try:
        db.session.delete(employee)
        db.session.commit()
        flash(f'✅ Employee "{name}" deleted!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error: {str(e)}', 'danger')
    
    return redirect(url_for('employees'))

# ========== ROLE MANAGEMENT ROUTES ==========

@app.route('/roles')
def roles():
    """Display all roles (excluding soft-deleted/inactive ones)"""
    try:
        # Show all roles including inactive for admin view
        all_roles = Role.query.order_by(Role.role_id.asc()).all()
        
        # Count recent roles (last 30 days)
        thirty_days_ago = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        recent_count = Role.query.filter(Role.created_at >= thirty_days_ago).count()
        
        return render_template('roles.html', roles=all_roles, recent_count=recent_count)
    except Exception as e:
        flash(f'Error loading roles: {str(e)}', 'danger')
        return render_template('roles.html', roles=[], recent_count=0)
@app.route('/role/create', methods=['POST'])
def create_role():
    """Create a new role - Only Admin can access (to be implemented)"""
    role_name = request.form.get('role_name')
    description = request.form.get('description')
    status = request.form.get('status') == '1'  # Get status from form
    
    if not role_name:
        flash('Role name is required!', 'danger')
        return redirect(url_for('roles'))
    
    # Check if role already exists
    existing_role = Role.query.filter_by(role_name=role_name).first()
    if existing_role:
        flash(f'Role "{role_name}" already exists!', 'danger')
        return redirect(url_for('roles'))
    
    role = Role(
        role_name=role_name,
        description=description,
        status=status  # Use status from form
    )
    
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
    """Get role details as JSON for editing"""
    role = Role.query.get_or_404(role_id)
    return jsonify({
        'role_id': role.role_id,
        'role_name': role.role_name,
        'description': role.description,
        'status': role.status
    })

@app.route('/role/update/<int:role_id>', methods=['POST'])
def update_role(role_id):
    """Update role details"""
    role = Role.query.get_or_404(role_id)
    
    role_name = request.form.get('role_name')
    description = request.form.get('description')
    status = request.form.get('status') == '1'
    
    if not role_name:
        flash('Role name is required!', 'danger')
        return redirect(url_for('roles'))
    
    # Check if name conflict (excluding current role)
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
    """Permanently delete role from database"""
    role = Role.query.get_or_404(role_id)
    role_name = role.role_name
    
    # Confirm dialog will be handled by JavaScript
    try:
        db.session.delete(role)
        db.session.commit()
        flash(f'✅ Role "{role_name}" has been permanently deleted from the database!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'❌ Error deleting role: {str(e)}', 'danger')
    
    return redirect(url_for('roles'))

@app.route('/test-roles')
def test_roles():
    """Test roles table and show all roles"""
    try:
        roles = Role.query.all()
        return f"""
        <h2>Roles Table Status</h2>
        <p>Total roles: {len(roles)}</p>
        <table border="1" cellpadding="10">
            <tr>
                <th>ID</th>
                <th>Role Name</th>
                <th>Description</th>
                <th>Status</th>
                <th>Created At</th>
            </tr>
            {''.join([f'<tr><td>{r.role_id}</td><td>{r.role_name}</td><td>{r.description or ""}</td><td>{"Active" if r.status else "Inactive"}</td><td>{r.created_at}</td></tr>' for r in roles])}
        </table>
        <br>
        <a href="/roles">Go to Role Management</a>
        """
    except Exception as e:
        return f"<h2>Error: {str(e)}</h2><p>Please run the SQL script to create the roles table.</p>"

# Add this new model after the Employee class
class Role(db.Model):
    __tablename__ = 'roles'
    role_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.String(200))
    status = db.Column(db.Boolean, default=True)  # True = active, False = inactive (soft delete)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


#  ADD USER MODEL HERE 
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'))
    role = db.relationship('Role', backref='users')


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

@app.route('/test-db')
def test_db():
    """Test MySQL connection and show table structure"""
    try:
        # Test connection
        db.session.execute(text('SELECT 1'))
        
        # Get table info
        departments_count = Department.query.count()
        employees_count = Employee.query.count()
        
        # Get column info
        result = db.session.execute(text("DESCRIBE departments"))
        columns = [row[0] for row in result.fetchall()]
        
        return f"""
        <h2>✅ MySQL Connection Successful!</h2>
        <p><strong>Database:</strong> hrm_system</p>
        <p><strong>Departments count:</strong> {departments_count}</p>
        <p><strong>Employees count:</strong> {employees_count}</p>
        <p><strong>Departments table columns:</strong> {', '.join(columns)}</p>
        <hr>
        <h3>Departments:</h3>
        <ul>
        {''.join([f'<li>{dept.name} - Manager: {dept.manager or "N/A"} - Budget: ₹{dept.budget}</li>' for dept in Department.query.all()])}
        </ul>
        <a href="/">Go to Dashboard</a>
        """
    except Exception as e:
        return f"""
        <h2>❌ Connection Failed</h2>
        <p><strong>Error:</strong> {str(e)}</p>
        <p><strong>Solution:</strong> Run the SQL script in MySQL Workbench to fix the table structure.</p>
        """

# Create add_department.html route if file doesn't exist
@app.route('/add_department_page')
def add_department_page():
    return render_template('add_department.html')

if __name__ == '__main__':
    with app.app_context():
        try:
            # Test MySQL connection without dropping tables
            db.session.execute(text('SELECT 1'))
            print("\n" + "="*60)
            print("✅ CONNECTED TO MySQL WORKBENCH")
            print("="*60)
            print(f"Database: hrm_system")
            print(f"Departments: {Department.query.count()}")
            print(f"Employees: {Employee.query.count()}")
            
            # Check columns
            result = db.session.execute(text("DESCRIBE departments"))
            columns = [row[0] for row in result.fetchall()]
            print(f"Table columns: {', '.join(columns)}")
            print("="*60)
            print("\n🚀 Server running on http://localhost:5000\n")
            
        except Exception as e:
            print("\n❌ MySQL Connection Failed!")
            print(f"Error: {e}")
            print("\nPlease run the SQL script in MySQL Workbench first.")
            exit(1)
    
    app.run(debug=True, port=5000)