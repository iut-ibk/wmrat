from django.contrib import admin
from django.urls import path
from django.contrib.auth import views as auth_views

from hub import views

urlpatterns = [
    # root
    path('', views.archive, name='archive'),

    # import network
    path('import', views.import_network, name='import_network'),

    # EPANET archive
    path('epanet_archive', views.epanet_archive, name='epanet_archive'),

    # explore network
    path('network/<int:network_id>/explore', views.explore, name='explore'),

    # export network (GIS files)
    path('network/<int:network_id>/export_gis', views.export_gis, name='export_gis'),

    # analysis archive
    path('archive', views.archive, name='archive'),

    # hub
    path('hub', views.archive, name='hub'),

    # new analysis
    path('new', views.new, name='new'),

    # download analysis
    path('analysis/<int:analysis_id>/download', views.download_analysis, name='download_analysis'),

    # delete analysis
    path('analysis/<int:analysis_id>/delete', views.delete, name='delete'),

    # delete network
    path('network/<int:network_id>/delete', views.delete_network, name='delete_network'),

    # cancel analysis
    path('analysis/<int:analysis_id>/cancel', views.cancel, name='cancel'),

    # visualize result
    path('analysis/<int:analysis_id>/visualize', views.visualize_result, name='visualize_result'),

    # utilize built-in login/logout views
    path('login/', auth_views.LoginView.as_view(template_name='login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='login'), name='logout'),

    # built-in admin interface
    path('admin/', admin.site.urls),
]
