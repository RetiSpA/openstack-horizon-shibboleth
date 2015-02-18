from django.conf import settings
import json
import requests
import logging
import os
import hashlib
from openstack_auth import utils
from keystoneclient import exceptions as keystone_exceptions
from collections import defaultdict
from openstack_auth import exceptions
from openstack_auth_shib import shib_global

LOG = logging.getLogger(__name__)
admin_token = getattr(settings, 'OPENSTACK_KEYSTONE_ADMIN_TOKEN')
admin_url = getattr(settings, 'OPENSTACK_KEYSTONE_ADMIN_URL')
current_user = os.environ['REMOTE_USER']
entitlements = os.environ['entitlement']

def admin_client():
	keystone_client = utils.get_keystone_client()
	client = keystone_client.Client(
		token = admin_token,
		endpoint=admin_url
		)
	return client
def get_user():
	client = admin_client()
	userlist = client.users.list()
	for user in userlist:
		if user.username==current_user:
			return user
	return None
def get_password(username):
	salt = getattr(settings,'SHIB_PASSWORD_SALT')
	password = hashlib.sha512(username+salt).hexdigest()
	return password

def update_password(user):
	client = admin_client()
	client.users.update_password(user,get_password(current_user))

def get_role(name):
	client = admin_client()
	roles = client.roles.list()
	for role in roles:
		if role.name == name:
			return role
	return None
def get_tenant(name):
	client = admin_client()
	tenants = client.tenants.list()
	for tenant in tenants:
		if tenant.name == name:
			return tenant
	return None

def update_roles(user):
	client = admin_client()
	entitlement_list = entitlements.split(";")
	ent_roles = defaultdict(list)

	for entitlement in entitlement_list:
		splitted = entitlement.split(":")
		rolename = splitted[len(splitted)-1]
		tenantname = splitted[len(splitted)-2]
		ent_roles[tenantname].append(rolename)

	new_tenants = list()
	for t in ent_roles.keys():
		tenant = get_tenant(t)
		if tenant is None:
			tenant = client.tenants.create(tenant_name=t)
		new_tenants.append(tenant)
	
	for r in ent_roles.keys():
		for rolename in ent_roles[r]:
			role = get_role(rolename)
			if role is None:
				client.roles.create(rolename)
	
	existing_tenants = client.tenants.list()
	for tenant in existing_tenants:
		if (user in tenant.list_users()):
			roles = user.list_roles(tenant)
			for role in roles:
				tenant.remove_user(user, role)
	for tenant in new_tenants:
		for rolename in ent_roles[tenant.name]:
			role = get_role(rolename)
			tenant.add_user(user,role)

def create_user():
	client = admin_client()
	newuser = client.users.create(name=current_user,password=get_password(current_user),email=os.environ['mail'])
	return newuser

def update_user():
	user = get_user()
	if user is None:
		user = create_user()
	update_roles(user)
	update_password(user)
	return current_user
