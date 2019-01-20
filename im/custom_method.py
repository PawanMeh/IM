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
		con_name = "Multiple issues raised: "
		for row in cur_issue.get("issue_split"):
			issue = frappe.new_doc("Issue")
			issue.subject = row.subject
			issue.raised_by = cur_issue.raised_by
			issue.email_account = cur_issue.email_account
			issue.issue_type = cur_issue.issue_type
			issue.issue_reference = cur_issue.name
			issue.insert(ignore_permissions=True)
			con_name = con_name + issue.name + " / "
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
		sender_email = frappe.db.get_value("Email Account",cur_issue.email_account, "email_id"):
		msg = """ Hi, <br><br> Issue - %s has been closed and multiple issues have been raised as per resolution: %s"""%(cur_issue.name, cur_issue.resolution_details)
		frappe.sendmail(sender = sender_email, recipients = [cur_issue.raised_by], subject = "Issue Close -'%s'"%(cur_issue.name), content = msg)