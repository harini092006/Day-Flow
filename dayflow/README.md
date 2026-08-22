# Dayflow – Human Resource Management System

## Project Overview

Dayflow is a centralized Human Resource Management System designed to simplify and digitize essential HR operations. The system provides a unified platform for managing employee information, attendance, leave, payroll, departments, job positions, and other HR activities.

The primary objective of Dayflow is to reduce manual HR processes, improve data accuracy, increase transparency, and provide an efficient workflow for both employees and HR administrators.

## Problem Statement

Traditional HR management often depends on paperwork, spreadsheets, and disconnected systems. These processes can make employee record management, attendance tracking, leave management, payroll processing, and HR reporting time-consuming and error-prone.

Organizations need a centralized system that can manage employee information and HR operations efficiently while providing different levels of access to employees and HR administrators.

Dayflow addresses these challenges by providing a centralized HR management platform with role-based access and organized HR workflows.

## Proposed Solution

Dayflow provides a single platform where employees and HR administrators can manage HR-related activities according to their respective roles.

The system brings essential HR operations together into one centralized platform, making it easier to manage employee information, attendance, leave, payroll, and HR-related activities.

The major areas of the system include:

* Employee Management
* Department and Job Position Management
* Attendance Management
* Leave Management
* Payroll Management
* Employee Records
* HR Dashboard and Analytics
* Role-Based Access Control

## Key Features

### Employee Management

* Create and manage employee profiles
* Maintain personal and professional information
* Manage departments and job positions
* Store employee records in a centralized system
* Provide easy access to employee information

### Attendance Management

* Record employee attendance
* Track working hours
* Maintain attendance history
* Monitor employee attendance status
* Provide attendance information to authorized users

### Leave Management

* Submit leave requests
* Review leave applications
* Approve or reject leave requests
* Track leave status
* Maintain leave history

### Payroll Management

* Maintain employee salary information
* Manage payroll records
* Organize employee salary details
* Provide structured payroll information
* Simplify payroll-related HR operations

### Dashboard and Analytics

* Display employee statistics
* Provide attendance overview
* Display leave statistics
* Provide centralized HR information
* Support HR decision-making through organized data

### Role-Based Access

The system provides different functionalities based on user roles.

#### Admin / HR

* Manage employees
* Manage departments
* Manage job positions
* Monitor attendance
* Manage leave requests
* Manage payroll
* Access HR information and reports

#### Employee

* View personal profile
* View attendance information
* Apply for leave
* Track leave status
* Access relevant personal HR information

## System Architecture

```text
Users
  |
  v
Dayflow User Interface
  |
  v
Odoo Application Layer
  |
  +------------------+------------------+
  |                  |                  |
  v                  v                  v
Employee          Attendance          Leave
Management        Management         Management
  |                  |                  |
  +------------------+------------------+
                     |
                     v
              Payroll Management
                     |
                     v
                PostgreSQL
                  Database
```

## Application Workflow

```text
                         Login
                           |
             +-------------+-------------+
             |                           |
             v                           v
         Admin / HR                  Employee
             |                           |
      +------+------+              +-----+------+
      |      |      |              |     |      |
      v      v      v              v     v      v
 Employee Attendance Leave       Profile Attendance Leave
 Management Management Management       Management Application
      |      |      |                    |          |
      +------+------+                    +----------+
             |
             v
          Payroll
             |
             v
         Analytics
```

## Project Objectives

* Digitize traditional HR processes
* Centralize employee information
* Simplify attendance management
* Simplify leave management
* Improve payroll management
* Reduce manual work and paperwork
* Reduce human errors
* Improve HR workflow efficiency
* Provide role-based access control
* Improve transparency between employees and HR
* Provide a scalable HR management solution

## Benefits

* Centralized HR operations
* Reduced manual processes
* Better organization of employee information
* Faster access to HR records
* Improved employee experience
* Improved transparency
* Reduced chances of data entry errors
* Structured HR workflows
* Easy management of employee-related activities

## Technology Stack

* Platform: Odoo
* Backend: Python
* Frontend: HTML, CSS, JavaScript
* Database: PostgreSQL
* Development Environment: Visual Studio Code
* Version Control: Git and GitHub

## Project Structure

```text
Dayflow/
│
├── README.md
├── models/
├── views/
├── controllers/
├── security/
├── static/
│   ├── css/
│   ├── js/
│   └── images/
├── data/
├── demo/
├── screenshots/
└── documentation/
```

## Future Enhancements

* AI-powered HR assistant
* Mobile application
* Advanced HR analytics
* Automated notifications
* Email integration
* Automated payslip generation
* Employee performance analytics
* Advanced reporting
* Enhanced security and audit management
* Integration with additional HR services

## Team

### Team Leader

**Harini S P**

Role: Team Leader and Developer

Contribution:

* Project planning
* Problem analysis
* System design
* Application development
* Module integration
* Testing
* Documentation
* Project presentation

### Team Member

**Dhanushiya**

Role: Team Member and Developer

Contribution:

* Application development
* Feature implementation
* Testing
* Documentation
* Project support

## Team Structure

| S.No | Name         | Role        |
| ---- | ------------ | ----------- |
| 1    | S.P. Harini  | Team Leader |
| 2    | S Dhanushiya | Team Member |

Project Name: Dayflow – Human Resource Management System

The project focuses on building a centralized and efficient HR management solution using the Odoo ecosystem. The system is designed to simplify HR operations, improve employee management, and provide an organized workflow for employees and HR administrators.

Project Link : https://day-flow.onrender.com
