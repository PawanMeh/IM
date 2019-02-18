from __future__ import unicode_literals
import frappe, json
import frappe.desk.form.meta
import frappe.desk.form.load

from frappe import _

@frappe.whitelist()
def make_multiple_issues(docname):
	cur_issue = frappe.get_doc("Issue", docname)
	issue_inserted = False
	if cur_issue.status in ["Open", "Replied"]:
		con_name = " "
		for row in cur_issue.get("issue_split"):
			issue = frappe.new_doc("Issue")
			issue.subject = row.subject
			issue.raised_by = cur_issue.raised_by
			issue.email_account = cur_issue.email_account
			issue.issue_type = cur_issue.issue_type
			issue.issue_reference = cur_issue.name
			issue.insert(ignore_permissions=True)
			con_name = row.subject + "-" + issue.name + " / " + con_name
			issue_inserted = True
		if issue_inserted:
			cur_issue.resolution_details = con_name
			cur_issue.status = "Closed"
			cur_issue.save()
		else:
			frappe.throw(_("Please check if you have entered rows in Issue Split Details and saved"))
	else:
		frappe.throw(_("Multiple Issues cannot be created for Issues in Closed or Hold status"))

	if cur_issue.raised_by and issue_inserted:
		sender_email = frappe.db.get_value("Email Account",cur_issue.email_account, "email_id")
		msg = """ Hi, <br><br>%s - Ticket No - %s has been split and replaced with the following new ticket numbers <br><br> %s"""%(cur_issue.subject, cur_issue.name, con_name)
		frappe.sendmail(sender = sender_email, recipients = [cur_issue.raised_by], subject = "%s - Ticket No - %s is split and replaced"%(cur_issue.subject, cur_issue.name), content = msg)

@frappe.whitelist()
def cc_list(docname):
	email_ids = frappe.db.sql('''select 
								a.cc
						from 
							`tabCommunication` a
						where
							a.reference_doctype = 'Issue'
							and a.reference_name = %s
							and a.creation = (select 
													max(b.creation)
												from 
													`tabCommunication` b
												where 
													a.reference_doctype = b.reference_doctype
													and a.reference_name = b.reference_name)
							and a.cc is NOT NULL''', docname, as_dict=1)

	if email_ids:
		pass
	else:
		email_ids = frappe.db.sql('''select 
									a.cc
							from 
								`tabCommunication` a, `tabIssue` b
							where
								a.reference_doctype = 'Issue'
								and a.reference_name = b.issue_reference
								and b.name = %s
								and a.creation = (select
														max(b.creation)
													from
														`tabCommunication` b
													where
														a.reference_doctype = b.reference_doctype
														and a.reference_name = b.reference_name)
								and a.cc is NOT NULL''', docname, as_dict=1)

	for cc in email_ids:
		if cc['cc']:
			return cc['cc']

def share_issue(self, method):
	old_user = frappe.db.get_value("Issue", filters={"name": self.name}, fieldname="user_assigned")
	issue_name = frappe.db.get_value("Issue", filters={"name": self.name}, fieldname="name")
	if old_user and issue_name:
		if self.user_assigned == old_user:
			pass
		else:
			if self.user_assigned:
				frappe.share.add(self.doctype, self.name, user = self.user_assigned, read = 1, write = 1, share = 1, notify = 1)
	if not old_user and self.user_assigned:
		frappe.share.add(self.doctype, self.name, user = self.user_assigned, read = 1, write = 1, share = 1, notify = 1)

	issue_status = frappe.db.get_value("Issue", filters={"name": self.name}, fieldname="status")
	split_issue = False
	for row in self.get("issue_split"):
		if row.subject:
			split_issue = True
			break


	if self.status == "Closed" and not self.ignore_closure_email:
		if issue_status == "Closed" or split_issue:
			pass
		else:
			sender_email = frappe.db.get_value("Email Account",self.email_account, "email_id")
			msg = """ Hi, <br><br> %s - Ticket No - %s has been closed. <br><br> Resolution details - %s <br><br>In case you do not agree with the closure kindly send a fresh email with reasons for your disagreement.
					<br><br>Kindly mention the following as your subject line. <br><br><b> %s - Ticket No - %s Closure is Disagreed <b>"""%(self.subject, self.name, self.resolution_details, self.subject, self.name)
			frappe.sendmail(sender = sender_email, recipients = [self.raised_by], subject = "%s - Ticket No - %s is Closed"%(self.subject,self.name), content = msg)

def update_issue_sent_to():
	frappe.db.sql("""update `tabIssue` c
							set c.issue_sent_to = (select 
													IFNULL(recipients, ' ') 
												from 
													`tabCommunication` a
												where
													a.reference_doctype = 'Issue'
													and a.reference_name = c.name
													and a.creation = (select 
																			min(b.creation)
																		from 
																			`tabCommunication` b
																		where 
																			a.reference_doctype = b.reference_doctype
																			and a.reference_name = b.reference_name)
													and a.recipients is NOT NULL
													and c.issue_sent_to IS NULL)
							where c.issue_sent_to IS NULL
							and exists (select 'X'
										from `tabCommunication` a
										where
											a.reference_doctype = 'Issue'
											and a.reference_name = c.name
											and a.creation = (select 
																	min(b.creation)
																from 
																	`tabCommunication` b
																where 
																	a.reference_doctype = b.reference_doctype
																	and a.reference_name = b.reference_name)
										and a.recipients is NOT NULL)
							""")

def send_reminder_email():
	email_ids = frappe.db.sql('''select 
								a.issue_sent_to as issue_sent, GROUP_CONCAT(CONCAT(a.name, "-", a.subject)) as issue
						from 
							`tabIssue` a
						where
							a.issue_sent_to IS NOT NULL
							and a.due_date IS NOT NULL
							and a.due_date < CURDATE()
							and a.status not in ('Closed')
							and a.ignore_closure_email = 1
						group by a.issue_sent_to''', as_dict=1)

	sender_email = frappe.db.get_value("Email Account",'Notifications', "email_id")

	for email_id in email_ids:
		msg = """ Hi, <br><br> Gentle Reminder <br><br> Your action is needed to close out the following issues <br><br>%s
				<br><br>Kindly contact our support team if you need any assistance. <br><br> Thanks & Regards <br><br> Team MVA"""%(email_id['issue'])
		frappe.sendmail(sender = sender_email, recipients = email_id['issue_sent'], subject = "MVA Reminder - Your action is needed to close out certain issues", content = msg)
