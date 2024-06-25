
def create_employee_attedance()
    employee_list = frappe.get_list("Employee",fields=['name','first_name','last_name','hourly_rate','designation'])
    attendance_data = {}
    for employee in employee_list:
        employee_fullname = employee.first_name
        
        if employee.last_name != '' and employee.last_name != None:
            employee_fullname = employee_fullname + " " + employee.last_name
            
        checkin_stack = []
        filters = {'employee': employee.name}
        filters['docstatus'] = 0
        filters['attendance'] = ['=','']
        
        attendance_data[employee_fullname] = {}
        checkin_list = frappe.get_list(doctype="Employee Checkin",filters=filters,fields=['name', 'time', 'log_type', 'employee'], order_by='time asc')
        print(f"{employee_fullname}: {len(checkin_list)}")
        attendance_data[employee_fullname]['attendance'] = {}
        attendance_data[employee_fullname]['working_hours'] = 0
        attendance_data[employee_fullname]['break_hours'] = 0
        attendance_data[employee_fullname]['status'] = "Off"
        
        for checkin in checkin_list:
            checkin_day = (checkin.time - timedelta(hours=5)).strftime('%Y/%m/%d')

            if str(checkin_day) not in attendance_data[employee_fullname]['attendance'].keys():
                if checkin.log_type == 'IN':
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
            if checkin.log_type == 'IN':
                attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = checkin
                attendance_data[employee_fullname]['status'] = "Working"
                checkin_stack.append(checkin)
            elif checkin.log_type == 'OUT':
                attendance_data[employee_fullname]['status'] = "Off"
                if len(checkin_stack) == 0:
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Check-out without check-in")
                else:
                    clock_in = checkin_stack.pop()
                    clockin_day = (clock_in.time - timedelta(hours=5)).strftime('%Y/%m/%d') 
                     
                    if ((checkin.time - timedelta(hours=5)).day - (clock_in.time - timedelta(hours=5)).day) > 1:
                        attendance_data[employee_fullname]['attendance'][str(clockin_day)]['issues'].append(clock_in.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Employee checked in for more than 2 days")    
                    else: #shift carry over till the next day                    
                        attendance_data[employee_fullname]['attendance'][str(clockin_day)]['check_out'] = checkin    
                    while len(checkin_stack) > 0:
                        clock_in = checkin_stack.pop()
                        attendance_data[employee_fullname]['attendance'][str(clockin_day)]['issues'].append(clock_in.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Checkin without checkout")
            elif checkin.log_type == 'Break-OUT':
                if str(checkin_day) not in attendance_data[employee_fullname]['attendance'].keys():
                    if len(checkin_stack) != 0:
                        checkin_day = (checkin_stack[-1].time - timedelta(hours=5)).strftime('%Y/%m/%d')
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'].append(checkin)
                        attendance_data[employee_fullname]['status'] = "On Break"
                    else:
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break-out without check-in")
                else:
                    attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'].append(checkin)
                    attendance_data[employee_fullname]['status'] = "On Break"
            elif checkin.log_type == 'Break-IN':
                if str(checkin_day) not in attendance_data[employee_fullname]['attendance'].keys():
                    if len(checkin_stack) != 0:
                        checkin_day = (checkin_stack[-1].time - timedelta(hours=5)).strftime('%Y/%m/%d')
                        if len(attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks']) != 0:
                            attendance_data[employee_fullname]['status'] = "Working"
                            attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'].append({'out':attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0], 'in':checkin})
                            del attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0]
                        else:
                            attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break in before break out")
                    else:
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)] = {}
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_in'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['check_out'] = None
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'] = []
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break-in without check-in")
   
                else:
                    if len(attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks']) != 0:
                        attendance_data[employee_fullname]['status'] = "Working"
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['break_log'].append({'out':attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0], 'in':checkin})
                        del attendance_data[employee_fullname]['attendance'][str(checkin_day)]['breaks'][0]
                    else:
                        attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Break in before break out")
            else:
                attendance_data[employee_fullname]['attendance'][str(checkin_day)]['issues'].append(checkin.time.strftime("%d/%m/%Y, %H:%M:%S") + " - Unknown checkin type")

        #per employee after calculations
        for day in attendance_data[employee_fullname]['attendance']:
            if len(attendance_data[employee_fullname]['attendance'][day]['issues']) == 0 and attendance_data[employee_fullname]['attendance'][day]['check_out'] != None:
                create_and_link_attendance(attendance_data[employee_fullname]['attendance'][day])


def create_and_link_attendance(attendances):
    company = frappe.get_list("Company")[0].name
    employee = attendances['check_in'].employee
    working_hours = round((attendances['check_out'].time - attendances['check_in'].time).seconds/36)/100

    attendance_doc = frappe.get_doc({
         'doctype' : 'Attendance',
         'attendance_date' : attendances['check_in'].time.date(),
         'employee' : employee,
         'company' : company,
         'employee_name':  frappe.get_doc("Employee",employee).employee_name,
         'working_hours': working_hours,
         'status': 'Present',
         'in_time': attendances['check_in'].time,
         'out_time': attendances['check_out'].time,
    })
    attendance_doc.save()
    checkin_log = [frappe.get_doc('Employee Checkin',attendances['check_in'].name)]
    total_break_hours = 0
    for break_entry in attendances['break_log']:
        break_out = break_entry['in']
        break_in = break_entry['out']
        checkin_log.append(frappe.get_doc('Employee Checkin',break_out.name))
        checkin_log.append(frappe.get_doc('Employee Checkin',break_in.name))
        if break_out.time > break_in.time:
            break_hours = round((break_out.time - break_in.time).seconds/36)/100
            attendance_doc.append('breaks',{'break_out':break_out.time, 'break_in': break_in.time})
        else:
            break_hours = round((break_in.time - break_out.time).seconds/36)/100
            attendance_doc.append('breaks',{'break_out':break_in.time, 'break_in': break_out.time})
        total_break_hours += break_hours
    attendance_doc.break_hours = total_break_hours
    checkin_log.append(frappe.get_doc('Employee Checkin',attendances['check_out'].name))
    for checkin in checkin_log:
        checkin.attendance = attendance_doc.name
        checkin.save()
        checkin.submit()
        
    attendance_doc.save()
    attendance_doc.submit()
    frappe.db.commit()
    