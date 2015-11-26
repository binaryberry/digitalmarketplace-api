import datetime

from flask import json
from nose.tools import assert_equal, assert_in
from dateutil.parser import parse as parse_time

from dmutils.audit import AuditTypes

from ..helpers import BaseApplicationTest
from app.models import db, Framework, SupplierFramework, DraftService, AuditEvent, Supplier, User


class TestListFrameworks(BaseApplicationTest):
    def test_all_frameworks_are_returned(self):
        with self.app.app_context():
            response = self.client.get('/frameworks')
            data = json.loads(response.get_data())

            assert_equal(response.status_code, 200)
            assert_equal(len(data['frameworks']),
                         len(Framework.query.all()))
            assert_equal(sorted(data['frameworks'][0].keys()),
                         ['framework', 'id', 'lots', 'name', 'slug', 'status'])


class TestGetFramework(BaseApplicationTest):
    def test_a_single_framework_is_returned(self):
        with self.app.app_context():
            response = self.client.get('/frameworks/g-cloud-7')
            data = json.loads(response.get_data())

            assert_equal(response.status_code, 200)
            assert_equal(data['frameworks']['slug'], 'g-cloud-7')
            assert_in('status', data['frameworks'])

    def test_framework_lots_are_returned(self):
        with self.app.app_context():
            response = self.client.get('/frameworks/g-cloud-7')

        data = json.loads(response.get_data())
        assert_equal(data['frameworks']['lots'], [
            {u'id': 1, u'name': u'Software as a Service', u'one_service_limit': False, u'slug': u'saas'},
            {u'id': 2, u'name': u'Platform as a Service', u'one_service_limit': False, u'slug': u'paas'},
            {u'id': 3, u'name': u'Infrastructure as a Service', u'one_service_limit': False, u'slug': u'iaas'},
            {u'id': 4, u'name': u'Specialist Cloud Services', u'one_service_limit': False, u'slug': u'scs'}
        ])

    def test_a_404_is_raised_if_it_does_not_exist(self):
        with self.app.app_context():
            response = self.client.get('/frameworks/biscuits-for-gov')

            assert_equal(response.status_code, 404)


class TestUpdateFramework(BaseApplicationTest):
    def setup(self):
        super(TestUpdateFramework, self).setup()
        framework = Framework()
        framework.name = 'Example G-Cloud framework'
        framework.framework = 'gcloud'
        framework.slug = 'example'
        framework.status = 'open'

        with self.app.app_context():
            db.session.add(framework)
            db.session.commit()

    def teardown(self):
        with self.app.app_context():
            Framework.query.filter(Framework.slug == 'example').delete()
            db.session.commit()

    def test_framework_updated(self):
        with self.app.app_context():
            response = self.client.post('/frameworks/example',
                                        data=json.dumps({'frameworks': {'status': 'expired'},
                                                         'updated_by': 'example user'}),
                                        content_type="application/json")

            assert response.status_code == 200
            assert Framework.query.filter(Framework.slug == 'example').first().status == "expired"

    def test_returns_404_on_non_existent_framework(self):
        with self.app.app_context():
            response = self.client.post('/frameworks/example2',
                                        data=json.dumps({'frameworks': {'status': 'expired'},
                                                         'updated_by': 'example user'}),
                                        content_type="application/json")

            assert response.status_code == 404

    def test_cannot_update_framework_with_invalid_status(self):
        with self.app.app_context():
            response = self.client.post('/frameworks/example',
                                        data=json.dumps({'frameworks': {'status': 'invalid'},
                                                         'updated_by': 'example user'}),
                                        content_type="application/json")

            assert response.status_code == 400

    def test_cannot_update_fields_other_than_status(self):
        with self.app.app_context():
            response = self.client.post('/frameworks/example',
                                        data=json.dumps({'frameworks': {'status': 'expired', 'name': 'Blah blah'},
                                                         'updated_by': 'example user'}),
                                        content_type="application/json")

            assert response.status_code == 400


class TestFrameworkStats(BaseApplicationTest):
    def make_declaration(self, framework_id, supplier_ids, status=None):
        with self.app.app_context():
            db.session.query(
                SupplierFramework
            ).filter(
                SupplierFramework.framework_id == framework_id,
                SupplierFramework.supplier_id.in_(supplier_ids)
            ).update({
                SupplierFramework.declaration: {'status': status}
            }, synchronize_session=False)

            db.session.commit()

    def register_framework_interest(self, framework_id, supplier_ids):
        with self.app.app_context():
            for supplier_id in supplier_ids:
                db.session.add(
                    SupplierFramework(
                        framework_id=framework_id,
                        supplier_id=supplier_id,
                        declaration={}
                    )
                )
            db.session.commit()

    def create_drafts(self, framework_id, supplier_id_count_pairs, status='not-submitted'):
        with self.app.app_context():
            for supplier_id, count in supplier_id_count_pairs:
                for ind in range(count):
                    db.session.add(
                        DraftService(
                            lot_id=1 + (ind % 4),
                            framework_id=framework_id,
                            supplier_id=supplier_id,
                            data={},
                            status=status
                        )
                    )

            db.session.commit()

    def create_users(self, supplier_ids, logged_in_at):
        with self.app.app_context():
            for supplier_id in supplier_ids:
                db.session.add(
                    User(
                        name='supplier user',
                        email_address='supplier-{}@user.dmdev'.format(supplier_id),
                        password='testpassword',
                        active=True,
                        password_changed_at=datetime.datetime.utcnow(),
                        role='supplier',
                        supplier_id=supplier_id,
                        logged_in_at=logged_in_at
                    )
                )

            db.session.commit()

    def setup_data(self, framework_slug):
        with self.app.app_context():
            framework = Framework.query.filter(Framework.slug == framework_slug).first()

        self.setup_dummy_suppliers(30)
        self.register_framework_interest(framework.id, range(20))
        self.make_declaration(framework.id, [1, 3, 5, 7, 9, 11], status='started')
        self.make_declaration(framework.id, [0, 2, 4, 6, 8, 10], status='complete')
        self.create_drafts(framework.id, [
            (1, 1),   # 1 saas; with declaration
            (2, 7),   # 1 of each + iaas, paas, saas; with declaration
            (3, 2),   # saas + paas; with declaration
            (14, 3),  # iaas + paas + saas; without declaration
        ])
        self.create_drafts(framework.id, [
            (1, 2),   # saas + paas; with declaration
            (2, 15),  # 3 of each + iaas, paas, saas; with declaration
            (3, 2),   # saas + paas; with declaration
            (14, 7),  # 1 of each + iaas + paas + saas; without declaration
        ], status='submitted')

        self.create_users(
            [1, 2, 3, 4, 5],
            logged_in_at=datetime.datetime.utcnow() - datetime.timedelta(days=1)
        )

        self.create_users(
            [6, 7, 8, 9],
            logged_in_at=datetime.datetime.utcnow() - datetime.timedelta(days=10)
        )

        self.create_users(
            [10, 11],
            logged_in_at=None
        )

    def test_stats(self):
        self.setup_data('g-cloud-7')

        response = self.client.get('/frameworks/g-cloud-7/stats')
        assert_equal(json.loads(response.get_data()), {
            u'services': [
                {u'count': 1, u'status': u'not-submitted',
                 u'declaration_made': False, u'lot': u'iaas'},
                {u'count': 2, u'status': u'not-submitted',
                 u'declaration_made': True, u'lot': u'iaas'},
                {u'count': 2, u'status': u'not-submitted',
                 u'declaration_made': False, u'lot': u'paas'},
                {u'count': 2, u'status': u'not-submitted',
                 u'declaration_made': True, u'lot': u'paas'},
                {u'count': 3, u'status': u'not-submitted',
                 u'declaration_made': False, u'lot': u'saas'},
                {u'count': 2, u'status': u'not-submitted',
                 u'declaration_made': True, u'lot': u'saas'},
                {u'count': 1, u'status': u'not-submitted',
                 u'declaration_made': True, u'lot': u'scs'},

                {u'count': 2, u'status': u'submitted',
                 u'declaration_made': False, u'lot': u'iaas'},
                {u'count': 4, u'status': u'submitted',
                 u'declaration_made': True, u'lot': u'iaas'},
                {u'count': 4, u'status': u'submitted',
                 u'declaration_made': False, u'lot': u'paas'},
                {u'count': 4, u'status': u'submitted',
                 u'declaration_made': True, u'lot': u'paas'},
                {u'count': 4, u'status': u'submitted',
                 u'declaration_made': False, u'lot': u'saas'},
                {u'count': 4, u'status': u'submitted',
                 u'declaration_made': True, u'lot': u'saas'},
                {u'count': 1, u'status': u'submitted',
                 u'declaration_made': False, u'lot': u'scs'},
                {u'count': 3, u'status': u'submitted',
                 u'declaration_made': True, u'lot': u'scs'},
            ],
            u'interested_suppliers': [
                {u'count': 7, u'declaration_status': None, u'has_completed_services': False},
                {u'count': 1, u'declaration_status': None, u'has_completed_services': True},
                {u'count': 5, u'declaration_status': 'complete', u'has_completed_services': False},
                {u'count': 1, u'declaration_status': 'complete', u'has_completed_services': True},
                {u'count': 4, u'declaration_status': 'started', u'has_completed_services': False},
                {u'count': 2, u'declaration_status': 'started', u'has_completed_services': True},
            ],
            u'supplier_users': [
                {u'count': 4, u'recent_login': False},
                {u'count': 2, u'recent_login': None},
                {u'count': 5, u'recent_login': True},
            ]
        })

    def test_stats_are_for_g_cloud_7_only(self):
        self.setup_data('g-cloud-6')
        response = self.client.get('/frameworks/g-cloud-7/stats')
        assert_equal(json.loads(response.get_data()), {
            u'interested_suppliers': [],
            u'services': [],
            u'supplier_users': [
                {u'count': 4, u'recent_login': False},
                {u'count': 2, u'recent_login': None},
                {u'count': 5, u'recent_login': True},
            ]
        })


class TestGetFrameworkSuppliers(BaseApplicationTest):
    def setup(self):
        super(TestGetFrameworkSuppliers, self).setup()

        self.setup_dummy_suppliers(5)
        with self.app.app_context():
            db.session.execute("UPDATE frameworks SET status='open' WHERE id=4")
            db.session.commit()
            for supplier_id in range(5):
                response = self.client.put(
                    '/suppliers/{}/frameworks/g-cloud-7'.format(supplier_id),
                    data=json.dumps({
                        'update_details': {'updated_by': 'example'}
                    }),
                    content_type='application/json')
                assert response.status_code == 201, response.get_data(as_text=True)
            for supplier_id in range(3, 5):
                response = self.client.post(
                    '/suppliers/{}/frameworks/g-cloud-7'.format(supplier_id),
                    data=json.dumps({
                        'update_details': {'updated_by': 'example'},
                        'frameworkInterest': {'agreementReturned': True},
                    }),
                    content_type='application/json')
                assert response.status_code == 200, response.get_data(as_text=True)

    def teardown(self):
        super(TestGetFrameworkSuppliers, self).teardown()

        with self.app.app_context():
            db.session.execute("UPDATE frameworks SET status='open' WHERE id=4")
            db.session.commit()

    def test_list_suppliers_related_to_a_framework(self):
        with self.app.app_context():
            response = self.client.get('/frameworks/g-cloud-7/suppliers')

            assert response.status_code == 200
            data = json.loads(response.get_data())
            assert len(data['supplierFrameworks']) == 5

    def test_list_suppliers_with_agreements_returned(self):
        with self.app.app_context():
            response = self.client.get('/frameworks/g-cloud-7/suppliers?agreement_returned=true')

            assert response.status_code == 200
            data = json.loads(response.get_data())
            assert len(data['supplierFrameworks']) == 2

            times = [parse_time(item['agreementReturnedAt']) for item in data['supplierFrameworks']]
            assert times[0] > times[1]


class TestGetFrameworkInterest(BaseApplicationTest):
    def setup(self):
        super(TestGetFrameworkInterest, self).setup()

        self.register_g7_interest(5)

    def register_g7_interest(self, num):
        self.setup_dummy_suppliers(num)
        with self.app.app_context():
            for supplier_id in range(num):
                db.session.add(
                    SupplierFramework(
                        framework_id=4,
                        supplier_id=supplier_id
                    )
                )
            db.session.commit()

    def test_interested_suppliers_are_returned(self):
        with self.app.app_context():
            response = self.client.get('/frameworks/g-cloud-7/interest')

            assert_equal(response.status_code, 200)
            data = json.loads(response.get_data())
            assert_equal(data['interestedSuppliers'], [0, 1, 2, 3, 4])

    def test_a_404_is_raised_if_it_does_not_exist(self):
        with self.app.app_context():
            response = self.client.get('/frameworks/biscuits-for-gov/interest')

            assert_equal(response.status_code, 404)
