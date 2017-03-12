# coding=utf-8
import bcrypt

from mycodo.mycodo_flask.extensions import db
from mycodo.databases import CRUDMixin


class User(CRUDMixin, db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.Integer, primary_key=True)
    user_name = db.Column(db.VARCHAR(64), unique=True, index=True)
    user_password_hash = db.Column(db.VARCHAR(255))
    user_email = db.Column(db.VARCHAR(64), unique=True, index=True)
    user_role = db.Column(db.Integer, db.ForeignKey('roles.id'), default=None)
    user_theme = db.Column(db.VARCHAR(64))

    roles = db.relationship("Role", back_populates="user")

    def __repr__(self):
        output = "<User: <name='{name}', email='{email}' is_admin='{isadmin}'>"
        return output.format(name=self.user_name, email=self.user_email, isadmin=bool(self.user_role == 1))

    def set_password(self, new_password):
        """ saves a password hash  """
        self.user_password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

    @staticmethod
    def check_password(password, hashed_password):
        """ validates a password """
        hashes_match = bcrypt.hashpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        return hashes_match
