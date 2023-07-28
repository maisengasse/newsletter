from setuptools import setup, find_packages
import os

version = '4.1'

setup(name='emencia.django.newsletter',
      version=version,
      description="A Django app for sending newsletter by email to a contact list.",
      long_description="Django Newsletter App",
      keywords='django, newsletter, mailing',
      classifiers=[
          'Intended Audience :: Developers',
          'Operating System :: OS Independent',
          'Programming Language :: Python',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'License :: OSI Approved :: BSD License',
          'Framework :: Django',
          ],

      author='Fantomas42',
      author_email='fantomas42@gmail.com',
      url='http://emencia.fr',

      license='BSD License',
      packages=find_packages(exclude=['ez_setup']),
      namespace_packages=['emencia', 'emencia.django'],
      include_package_data=True,
      zip_safe=False,
      install_requires=[
          'Django>=1.5',
          'setuptools',
          'html2text',
          'xlwt',
      ],
      entry_points="""
      # -*- Entry points: -*-
      """,
      )
