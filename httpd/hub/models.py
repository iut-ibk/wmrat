from django.db import models
from django.contrib.auth.models import AbstractUser

class WMRatUser(AbstractUser):
    pass

class WMNetwork(models.Model):
    # name
    name = models.CharField(max_length=64)

    # EPANET input data
    # TODO: filefield, charfield?
    # epanet_data = models.CharField(max_length=500000000)

    #NOTE: or: epanet_data = models.FileField(upload_to='networks')

    # optional parameter data
    opt_param = models.JSONField()

    # upload date
    uploaded_at = models.DateTimeField(auto_now_add=True)

class Analysis(models.Model):
    # analysis name
    name = models.CharField(max_length=64)

    # analysis type
    analysis_type = models.CharField(max_length=64)

    # user
    user = models.ForeignKey(WMRatUser, on_delete=models.RESTRICT)

    # network
    wm_network = models.ForeignKey(WMNetwork, on_delete=models.RESTRICT)

    # input
    input_json = models.JSONField()

    # processing stati
    STATUS_SUCCESS = 0
    STATUS_FAILED = 1
    STATUS_QUEUED = 2
    STATUS_PROCESSING = 3
    STATUS_CANCELLED = 4
    STATUS_CANCELLING = 5

    STATUS = (
        (STATUS_SUCCESS, 'Success'),
        (STATUS_FAILED, 'Failed'),
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_CANCELLED, 'Cancelled'),
        (STATUS_CANCELLING, 'Cancelling'),
    )

    # processing status
    proc_status = models.PositiveSmallIntegerField(choices=STATUS)

    # RQ job (uuid4)
    job_id = models.CharField(max_length=36)

    # processing id
    proc_pid = models.IntegerField(blank=True, null=True)

    # submission date
    submitted = models.DateTimeField()

    # processing duration
    duration_s = models.FloatField() 

    # info message
    info_msg = models.CharField(max_length=256)

    def get_analysis_status_str(self):
        return Analysis.STATUS[self.proc_status][1]

