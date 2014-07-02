import logging
import os
import re
import yaml

import scraper

from popit import PopIt
from scraper import MP
from slumber.exceptions import HttpClientError


BASE_DIR = os.path.dirname(__file__)

log = logging.getLogger(__name__)


def main():
    config = yaml.load(open(os.path.join(BASE_DIR, 'config.yml'), 'r'))

    api = PopIt(instance=config.get('POPIT_INSTANCE'),
                hostname=config.get('POPIT_HOSTNAME', 'popit.mysociety.org'),
                port=config.get('POPIT_PORT', 80),
                api_version='v0.1',
                user=config.get('POPIT_EMAIL'),
                password=config.get('POPIT_PASSWORD'))    

    init(api) # cleanup

    parliament = create_parliament(api)
    create_parties(api)
    create_committees(api)

    with open('data/mps.yml', 'r') as fl: # read mps yaml file created by scraper
        for data in yaml.load(fl):
            person = create_person(api, data)
            constituency = data['constituency']
            _, _, party_id = party_keys(data['party'])
            # ?? why do I need an empty id property to be valid? Popolo spec needs change?
            area = {'name': constituency, 'id':''} 
            create_membership(api, party_id, person['id'], area=area)
            create_membership(api, parliament['id'], person['id'], 
                role='Member', label='MP for %s' % constituency, 
                area=area)
            # TODO: create committee memberships

def create_parliament(api):
    # Organizations in PopIt can have pre-defined posts that members can then fill. 
    # TODO: predefined parliamentary posts (leadership etc)
    links = (
        {'url': 'http://www.parliament.gh', 'note': 'Official Parliament Website'},
    )

    return create_organization(api, name='Parliament of Ghana', 
                                    classification='house',
                                    links=links,
                                    id='org.odekro/house/4')['result']

def create_parties(api):
    with open('data/political-parties.txt', 'r') as fl:
        for name in fl.readlines():
            abbreviation, slug, party_id = party_keys(name)
            create_organization(api, name, 
                                classification='party', 
                                abbreviation=abbreviation,
                                slug=slug, id=party_id)

def party_keys(name):
    abbreviation = ''.join([x[0] for x in name.split()])
    slug = abbreviation.lower()
    return (abbreviation, slug, 'org.odekro/party/%s' % slug)

def create_committees(api):
    # All committees have the following posts;
    # Chair, Vice-Chair, Ranking Member and Deputy Ranking Member
    # TODO: prepopulate posts?
    for kind in ('standing', 'select'):
        with open('data/%s-committees.txt' % kind) as fl:
            for name in fl.readlines():
                create_committee(api, name, kind)

def create_committee(api, name, kind):
    return create_organization(api, name, classification='committee',
                               kind=kind,
                               slug=scraper.slugify(name),
                               id='org.odekro/committee/%s' % scraper.slugify(committee_key(name)))

def create_organization(api, name, classification=None, **kwargs):
    info = {'name': name, 'classification': classification}
    info.update(kwargs)
    return api.organizations.post(info)

def create_person(api, data):
    contacts = []
    for key in ('email', 'phone'):
        val = data.get(key, None)
        if val:
            contacts.append({'type': key, 'value': val})

    names = data['full_name'].split()
    person = {
        'name': data['full_name'],
        'family_name': names[-1],
        'given_names': ' '.join(names[:-1]),
        'honorific_prefix': data['title'],
        'slug': scraper.slugify(data['full_name']),
        'contact_details': contacts,
        # 'birth_date': None,
        # 'death_date': None,
        # 'summary': ''
    }
    try:
        return api.persons.post(person)['result']
    except HttpClientError, e:
        print '>>>>', e.response, e.content

def create_membership(api, org_id, person_id, **kwargs):
    info = {'organization_id': org_id, 'person_id': person_id}
    info.update(kwargs)
    try:
        return api.memberships.post(info)
    except HttpClientError, e:
        print '>>>>', e.response, e.content

def init(api):
    endpoints = [api.organizations, api.persons, api.memberships]

    # clean
    for endpoint in endpoints:
        for id in [x for x in [x.get('id', None) for x in endpoint.get().get('result', [])] if x is not None]:
            r = endpoint(id)
            # hack to remove trailing slash from resource url
            r._store['append_slash'] = False
            r.delete()

        for endpoint in endpoints:
            try:
                assert endpoint.get()['total'] is 0
            except AssertionError, e:
                print '>>>>', e,  endpoint.get()['total']
                raise

def committee_key(name):
    pattern = re.compile(r'\b(in|on|of|and|the)\b', flags=re.IGNORECASE)
    return scraper.slugify(pattern.sub('', committee_name(name)))

def committee_name(name):
    w = 'Committee'
    if name.startswith(w):
        return name[len(w) + 4:].strip() # remove committee on/of
    elif name.endswith(w):
        return name[:-len(w)].strip() # remove committee suffix
    return name

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, format='[gh-mps | %(levelname)s] %(message)s')
    log.setLevel(logging.DEBUG)
    main()
