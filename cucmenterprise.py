#!/usr/bin/env python

"""CUCM Update Enterprise Parameters

A PythonTk GUI program to update enterprise parameters on a Cisco Call Manager cluster via AXL


J. Worden (jeremy.worden@gmail.com)
2017

"""
import sys
import os
import suds
from suds.client import Client
from suds.xsd.doctor import Import
from suds.xsd.doctor import ImportDoctor
import ssl
import logging
import tkinter as tk
from tkinter import *
from tkinter import scrolledtext
from tkinter.filedialog import askopenfilename
import sqlite3 as lite
import operator
import subprocess
from tkinter import simpledialog as sdg
from suds.transport.https import HttpAuthenticated
from suds.client import WebFault
import urllib


# ignore ssl pain - python 2.7.9+ only
#ssl._create_default_https_context = ssl._create_unverified_context

try:
	_create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
	# Legacy Python that doesn't verify HTTPS certificates by default
	pass
else:
	# Handle target environment that doesn't support HTTPS verification
	ssl._create_default_https_context = _create_unverified_https_context

# set suds logging to critical only
logging.getLogger('suds.client').setLevel(logging.CRITICAL)

#global list variable
list = []


class popupWindow(object):
	def __init__(self,master):
		top=self.top=Toplevel(master)
		self.l=Label(top,text="Add Enterprise Parameter")
		self.l.pack()
		self.serverlbl = Label(top,text="Enter Server Name:")
		self.serverlbl.pack()
		self.server=Entry(top)
		self.server.pack()
		self.namelbl = Label(top,text="Enter Enterprise Paramater Name:")
		self.namelbl.pack()
		self.name=Entry(top)
		self.name.pack()
		self.paramvaluelbl = Label(top,text="Enter Enterprise Paramater Value:")
		self.paramvaluelbl.pack()
		self.paramvalue=Entry(top)
		self.paramvalue.pack()
		self.b=Button(top,text='Enter',command=self.cleanup)
		self.b.pack()
	def cleanup(self):
		self.value=self.server.get()
		self.value1=self.name.get()
		self.value2=self.paramvalue.get()
		self.top.destroy()

class Table(Frame):
	def __init__(self, parent):
		Frame.__init__(self, parent)
		self.CreateUI()
		#self.LoadTable()
		self.grid(sticky = (N,S,W,E))
		parent.grid_rowconfigure(0, weight = 1)
		parent.grid_columnconfigure(0, weight = 1)
		

	def CreateUI(self):
		from tkinter.ttk import Treeview
		param = Treeview(self)
		param['columns'] = ('parametername', 'paramvalue', 'updatedvalue')
		param.heading("#0", text='Server', anchor='w')
		param.column("#0", anchor="w", minwidth=0,width=150, stretch=NO)
		param.heading('parametername', text='Parameter Name')
		param.column('parametername', anchor="w",minwidth=0,width=350,stretch=NO)
		param.heading('paramvalue', text='Parameter Value')
		param.column('paramvalue', anchor="w",minwidth=0,width=100,stretch=NO)
		param.heading('updatedvalue', text='Updated Value')
		param.column('updatedvalue', anchor='center')
		param.grid(sticky = (N,S,W,E))
		self.treeview = param
		self.grid_rowconfigure(0, weight = 1)
		self.grid_columnconfigure(0, weight = 1)
		self.treeview.bind("<Double-Button-1>", self.TableItemClick)
	
	def clearTable(self):
		self.treeview.delete(*self.treeview.get_children())

	def LoadTable(self,server,name,value,newval):
		self.treeview.insert('', 'end', text=server, values=(name,value,newval))
		
	def TableItemClick(self,event):
		global list
		item = self.treeview.selection()[0]
		server = self.treeview.item(item,'text')
		settings = self.treeview.item(item,'values')
		curItem = self.treeview.focus()
		list = curItem
		update = sdg.askstring("Enter Enterprise Parameter", "Input updated parameter:")
		self.updateTable(list, server, settings[0],settings[1], update)
		
	def updateTable(self,item,server,name,value,newval):
		self.treeview.item(item, text=server, values=(name,value,newval))
		
	def getTable(self):
		children = self.treeview.get_children()
		s = []
		for index, child in enumerate(children):
			r = self.treeview.item(child)["values"]
			r.insert(0,self.treeview.item(child)["text"])
			s.append(r)
		
		return s


class CreateToolTip(object):
	'''
	create a tooltip for a given widget
	'''
	def __init__(self, widget, text='widget info'):
		self.widget = widget
		self.text = text
		self.widget.bind("<Enter>", self.enter)
		self.widget.bind("<Leave>", self.close)
	def enter(self, event=None):
		x = y = 0
		x, y, cx, cy = self.widget.bbox("insert")
		x += self.widget.winfo_rootx() + 25
		y += self.widget.winfo_rooty() + 20
		# creates a toplevel window
		self.tw = tk.Toplevel(self.widget)
		# Leaves only the label and removes the app window
		self.tw.wm_overrideredirect(True)
		self.tw.wm_geometry("+%d+%d" % (x, y))
		label = tk.Label(self.tw, text=self.text, justify='left',
					   background='#FFFFEA', relief='solid', borderwidth=1)
		label.pack(ipadx=1)
	def close(self, event=None):
		if self.tw:
			self.tw.destroy()
			
#console logger widget
class WidgetLogger(logging.Handler):
	def __init__(self, widget):
		logging.Handler.__init__(self)
		self.logging_text_widget = widget
		self.logging_text_widget.config(state='disabled')
		self.logging_text_widget.tag_config("DEBUG", foreground="grey")
		self.logging_text_widget.tag_config("INFO", foreground="black")
		self.logging_text_widget.tag_config("WARNING", foreground="orange")
		self.logging_text_widget.tag_config("ERROR", foreground="red")
		self.logging_text_widget.tag_config("CRITICAL", foreground="red", underline=1)


	def emit(self, record):
		self.logging_text_widget.config(state='normal')
		# Append message (record) to the widget
		self.logging_text_widget.insert(tk.END, self.format(record) + '\n', record.levelname)
		self.logging_text_widget.see(tk.END)  # Scroll to the bottom
		self.logging_text_widget.config(state='disabled')
		self.logging_text_widget.update() # Refresh the widget


def gui():
	#suds static variables for Cisco AXL connections
	tns = 'http://schemas.cisco.com/ast/soap/'
	imp = Import('http://schemas.xmlsoap.org/soap/encoding/','http://schemas.xmlsoap.org/soap/encoding/')
	imp.filter.add(tns)
	#get directory structure
	cwd = os.getcwd()
	
	#connect to db
	con = lite.connect('db/axl_connections.db')
	
	#module to insert in new AXL connections
	def insertSQL():
		name = nameentry.get()
		if name:
			#create blank list and add entries from GUI
			connections = []
			connections.append(nameentry.get())
			connections.append(var.get())
			connections.append(ipentry.get())
			connections.append(unentry.get())
			connections.append(pwentry.get())	
			with con:
				try:
					#connect to database and insert in connections, update console
					cur = con.cursor()
					cur.executemany('''INSERT INTO connections(name, version,ip_address,axl_username,axl_password) VALUES(?,?,?,?,?)''', [connections])
					logger.info('Successfully added ' + connections[0])
					con.commit()
				except Exception as e:
					#update console window if there are any errors or duplicates
					logger.critical(e)
			#refresh GUI dropdown	
			updateOption()
		else:
			return

			
	def returnSQL():
		#reset list and update with newly created connections
		savedaxl[:] = []
		savedaxl.insert(0,"Select AXL Connection")
		with con:    
			con.row_factory = lite.Row # its key
			cur = con.cursor()    
			cur.execute("SELECT name FROM connections")
			rows = cur.fetchall()
			for row in rows:
				data = "%s" % (row["name"])
				savedaxl.append(data)
	
	def loadAXL():
		#get selected variable from GUI
		optionSelected = var1.get()
		#do nothing if a selection is not made
		if optionSelected != "Select AXL Connection":
			with con:    
				#connect to database and select row based on selected	
				cur = con.cursor()    
				cur.execute("SELECT * FROM connections where name=?", (optionSelected,))
				rows = cur.fetchone()
			
			#Update GUI entries from database
			nameentry.delete(0,END)
			nameentry.insert(1,optionSelected)
			logger.info('Loaded Saved AXL Connection : ' + optionSelected)	
			var.set(rows[2])
			ipentry.delete(0,END)
			ipentry.insert(1,rows[3])
			unentry.delete(0,END)
			unentry.insert(1,rows[4])
			pwentry.delete(0,END)
			pwentry.insert(1,rows[5])
		else:
			#If no selection is made just return to GUI
			return
	
	def connectAXL():
		#AXL connection module variables
		d = dict();
		d['location'] = 'https://'+ ipentry.get() +':8443/axl/'
		d['username'] = unentry.get()
		d['password'] = pwentry.get()
		d['wsdl'] = "file://" + os.path.join(cwd,"schema/current/AXLAPI.wsdl")
		return d

		
	def axlSQL():
		#get AXL information from GUI
		info  = connectAXL()
		location = info.get('location')
		username = info.get('username')
		password = info.get('password')
		wsdl = info.get('wsdl')
		t = HttpAuthenticated(username=username, password=password)
		t.handler = urllib.request.HTTPBasicAuthHandler(t.pm)
		ssl_def_context = ssl.create_default_context()
		ssl_def_context.check_hostname = False
		ssl_def_context.verify_mode = ssl.CERT_NONE
		ssl_def_context.set_ciphers('HIGH:!DH:!aNULL')
		t1 = urllib.request.HTTPSHandler(context=ssl_def_context)
		t.urlopener = urllib.request.build_opener(t.handler, t1)
		try:
			client = Client(wsdl,location=location,plugins=[ImportDoctor(imp)],transport=t)
			try:
				result= client.service.executeSQLQuery("select ProcessNode.name as ProcessNode, ProcessConfig.paramname,ProcessConfig.paramvalue as ProcessConfig from processconfig,processnode where ProcessConfig.fkprocessnode = ProcessNode.pkid")
				car.clearTable()
				for node in result['return']['row']:
					car.LoadTable(str(node['processnode']),str(node['paramname']),str(node['processconfig']),'')
			except Exception as e:
				logger.critical(e)
		except Exception as e:
			logger.critical(e)
	
	def axlupdateSQL(server,name,newval):
			#get AXL information from GUI
			info  = connectAXL()
			location = info.get('location')
			username = info.get('username')
			password = info.get('password')
			wsdl = info.get('wsdl')
			t = HttpAuthenticated(username=username, password=password)
			t.handler = urllib.request.HTTPBasicAuthHandler(t.pm)
			ssl_def_context = ssl.create_default_context()
			ssl_def_context.check_hostname = False
			ssl_def_context.verify_mode = ssl.CERT_NONE
			ssl_def_context.set_ciphers('HIGH:!DH:!aNULL')
			t1 = urllib.request.HTTPSHandler(context=ssl_def_context)
			t.urlopener = urllib.request.build_opener(t.handler, t1)
			try:
				client = Client(wsdl,location=location,plugins=[ImportDoctor(imp)],transport=t)
				try:
					sqlStr = "update processconfig set paramvalue ='" + newval +"' where paramname = '" + name + "' and ProcessConfig.fkprocessnode = (select ProcessNode.pkid from Processnode where ProcessNode.name='" + server + "')"
					result= client.service.executeSQLUpdate(sqlStr)	
					logger.info("Successfully updated " + name + " to '" + newval + "' on " + server)
				except Exception as e:
					logger.critical(e)
			except Exception as e:
				logger.critical(e)
				
	def axlinsertSQL(server,name,newval):
				#get AXL information from GUI
				info  = connectAXL()
				location = info.get('location')
				username = info.get('username')
				password = info.get('password')
				wsdl = info.get('wsdl')
				t = HttpAuthenticated(username=username, password=password)
				t.handler = urllib.request.HTTPBasicAuthHandler(t.pm)
				ssl_def_context = ssl.create_default_context()
				ssl_def_context.check_hostname = False
				ssl_def_context.verify_mode = ssl.CERT_NONE
				ssl_def_context.set_ciphers('HIGH:!DH:!aNULL')
				t1 = urllib.request.HTTPSHandler(context=ssl_def_context)
				t.urlopener = urllib.request.build_opener(t.handler, t1)
				try:
					client = Client(wsdl,location=location,plugins=[ImportDoctor(imp)],transport=t)
					try:
						sqlStr = "insert into processconfig(paramvalue,paramname,tkservice,tkparam,fkprocessnode) values ('" + newval +"','" + name + "','0','2',(select ProcessNode.pkid from Processnode where ProcessNode.name='" + server + "'))"
						result= client.service.executeSQLUpdate(sqlStr)	
						logger.info("Successfully inserted " + name + " to '" + newval + "' on " + server)
					except Exception as e:
						logger.critical(e)
				except Exception as e:
					logger.critical(e)
				

	def button_testaxl_callback():
		info  = connectAXL()
		location = info.get('location')
		username = info.get('username')
		password = info.get('password')
		wsdl = info.get('wsdl')
		t = HttpAuthenticated(username=username, password=password)
		t.handler = urllib.request.HTTPBasicAuthHandler(t.pm)
		ssl_def_context = ssl.create_default_context()
		ssl_def_context.check_hostname = False
		ssl_def_context.verify_mode = ssl.CERT_NONE
		ssl_def_context.set_ciphers('HIGH:!DH:!aNULL')
		t1 = urllib.request.HTTPSHandler(context=ssl_def_context)
		t.urlopener = urllib.request.build_opener(t.handler, t1)
		try:
			client = Client(wsdl,location=location,plugins=[ImportDoctor(imp)],transport=t)
			resp = client.service.getCCMVersion()
			version = resp['return'].componentVersion.version
			logger.info('Successfully tested to Call Manager : ' + version)
		except Exception as e:
			logger.error('Failed to connect to ' + location)
			logger.critical(e)
			

	root = tk.Tk()
	root.resizable(width=False,height=False);
	root.title("CUCM AXL Update Enterprise Parameter Tool")
	
	#Area 1
	areaOne = LabelFrame(root)
	areaOne.grid_columnconfigure(0, weight=1)
	areaOne.grid(row=0, columnspan=3, sticky='WE', padx=5, pady=5, ipadx=5, ipady=5)
	Label(areaOne, text="Name your connection: ").grid(row=0,sticky=W,padx=5, pady=2)
	nameentry = Entry(areaOne)
	nameentry.grid(row=0,column=1,padx=5, pady=5)
	var = StringVar(areaOne)
	# Use dictionary for different call manager versions
	choices = {
		'8.5':0,
		'8.6':1,
		'9.0':2,
		'9.1':3,
		'10.0':4,
		'10.5':5,
		'11.0':6,
		'11.5':7,
	}
	option = OptionMenu(areaOne, var, *choices)
	var.set('8.5')
	option.configure(takefocus=1)
	Label(areaOne, text="CUCM Version: ").grid(row=1,sticky=W,padx=5, pady=2)
	option.grid(row = 1, column =1,sticky='NWES',columnspan=2)
	Label(areaOne, text="CUCM IP Address: ").grid(row=2,sticky=W,padx=5, pady=2)
	ipentry = Entry(areaOne)
	Label(areaOne, text="AXL Username: ").grid(row=3,sticky=W,padx=5, pady=2)
	unentry = Entry(areaOne)
	Label(areaOne, text="AXL Password: ").grid(row=4,sticky=W,padx=5, pady=2)
	pwentry = Entry(areaOne, show="*")
	ipentry.grid(row=2,column=1,padx=5, pady=5)
	unentry.grid(row=3,column=1,padx=5, pady=5)
	pwentry.grid(row=4,column=1,padx=5, pady=5)
	
	#Area 2
	areaTwo = LabelFrame(root)
	areaTwo.grid_columnconfigure(0, weight=1)
	areaTwo.grid(row =0,column=3, rowspan=4, columnspan=4,sticky='NWES', padx=5, pady=5)
	imageAdd = PhotoImage(file = 'images/add.gif')
	imageLoad = PhotoImage(file = 'images/load.gif')
	imageTest = PhotoImage(file = 'images/test.gif')
	imageRun = PhotoImage(file = 'images/run.gif')
	button_save = Button(areaTwo,image=imageAdd,command=insertSQL)
	button_save.grid(row=0,sticky="W")
	button_load = Button(areaTwo,image=imageLoad,command=loadAXL)
	button_load.grid(row=0,column=1,sticky="W")
	button_test = Button(areaTwo,image=imageTest,command=button_testaxl_callback)
	button_test.grid(row=0,column=2,sticky="W")
	button_run = Button(areaTwo,image=imageRun,command=axlSQL)
	button_run.grid(row=0,column=3,sticky="W")
	CreateToolTip(button_run, "Get Enterprise Parameters from CUCM")
	CreateToolTip(button_save, "Save AXL Connection")
	CreateToolTip(button_load, "Load AXL Connection from dropdown below")
	CreateToolTip(button_test, "Test AXL Connection")	
	#Saved AXL Connection Drop Down
	var1 = StringVar(areaTwo)
	savedaxl = ['']
	returnSQL() #Get Saved Names from DB
	var1.set(savedaxl[0])
	axloption = OptionMenu(areaTwo, var1, *savedaxl)
	axloption.configure(takefocus=1)
	axloption.grid(row = 3, column =0,columnspan=4,sticky="NWES")
	imageEx = PhotoImage(file = 'images/cisco.gif')
	Label(areaTwo, image=imageEx).grid(row=4,column=0,columnspan=4,sticky="NWES")
	
	def updateOption():
		# Reset var and delete all old options
		var1.set('')
		savedaxl[:] = []
		axloption['menu'].delete(0, 'end')
		returnSQL()
		#axloption = OptionMenu(areaTwo, var1, *savedaxl)

		# Insert list of new options (tk._setit hooks them up to var)
		for choice in savedaxl:
			axloption['menu'].add_command(label=choice, command=tk._setit(var1, choice))
			
		var1.set(savedaxl[0])
	
	
	#Area 3
	areaThree = LabelFrame(root)
	areaThree.grid_columnconfigure(0, weight=1)
	areaThree.grid_rowconfigure(0, weight=1)
	areaThree.grid(row=5, rowspan=10,columnspan=7, sticky='NWES', padx=5, pady=5, ipadx=5, ipady=5)
	car = Table(areaThree)
	car.grid(columnspan=7)
	
	def insertTable():
		w=popupWindow(root)
		root.wait_window(w.top)
		car.LoadTable(w.value, w.value1, "",w.value2)
	
	def getTable():
		values = car.getTable()
		for value in values:
			if value [2] and value[3]:				
				axlupdateSQL(value[0],value[1],str(value[3]))
				
			if not value[2] and value[3]:
				axlinsertSQL(value[0],value[1],str(value[3]))
	
				
		#refresh Table after updating
		logger.info("Refreshing Table with Updated Parameters")
		axlSQL()
		logger.info("Done!")
		
	imageUpdate = PhotoImage(file = 'images/update.gif')
	button_update = Button(areaThree,image=imageUpdate,command=getTable)
	button_update.grid(row=15,column=0,sticky="EW")
	button_update.grid_columnconfigure(0, weight=0)
	CreateToolTip(button_update, "Send Updates to CUCM Database")
	imageAddDB = PhotoImage(file = 'images/insert.gif')
	button_adddb = Button(areaThree,image=imageAddDB,command=insertTable,width=400,height=34)
	button_adddb.grid(row=15,column=2,sticky="EW")
	CreateToolTip(button_adddb, "Insert Parameter into table")
	
	
	#Area 4
	areaFour= LabelFrame(root)
	areaFour.grid_columnconfigure(0, weight=1)
	areaFour.grid_rowconfigure(0, weight=1)
	areaFour.grid(row=16, columnspan=7, sticky='NSEW', padx=5, pady=5, ipadx=5)
	st = tk.scrolledtext.ScrolledText(areaFour,state='normal',height=4)
	st.configure(font='TkFixedFont')
	st.grid(row=10,sticky='NSEW', columnspan=7)
	# Create textLogger
	text_handler = WidgetLogger(st)
	# Add the handler to logger
	logger = logging.getLogger()
	logger.addHandler(text_handler)
	logger.setLevel(logging.INFO)
	# Log some messages
	logger.info('Press Run button to retrieve Enterprise Parameters')
	
	#print grid areas for reference
#	print(areaOne.grid_size())
#	print(areaTwo.grid_size())
#	print(areaThree.grid_size())
#	print(areaFour.grid_size())
	
	menu = Menu(root)
	root.config(menu=menu)
	filemenu = Menu(menu)
	menu.add_cascade(label="File", menu=filemenu)
	filemenu.add_command(label="Exit", command=root.quit)
	
	root.columnconfigure(0, weight=1)
	mainloop()

if __name__ == "__main__":
	""" Run as a stand-alone script """
	gui()    