"""Compliance OS — REST API Views."""
from django.db.models import Avg, Count, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authentication.permissions import IsAdmin, IsTeamLeadOrAdmin
from api.models import Norme, Rule


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def compliance_audit_log_api(request):
    from compliance.models import AuditLog
    qs = AuditLog.objects.all()
    if request.query_params.get('entity_type'): qs = qs.filter(entity_type=request.query_params['entity_type'])
    if request.query_params.get('entity_id'):   qs = qs.filter(entity_id=request.query_params['entity_id'])
    if request.query_params.get('action'):       qs = qs.filter(action=request.query_params['action'])
    if request.query_params.get('performed_by'): qs = qs.filter(performed_by__icontains=request.query_params['performed_by'])
    try:
        limit = min(500, int(request.query_params.get('limit', 100)))
    except (ValueError, TypeError):
        limit = 100
    items = list(qs.values('id','entity_type','entity_id','action','old_value','new_value',
                            'performed_by','performed_at','reason','ip_address')[:limit])
    return Response({'total': qs.count(), 'items': items})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_coverage_api(request):
    from compliance.services import compute_coverage
    results = [compute_coverage(n.id) for n in Norme.objects.all()]
    return Response({'standards': results})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_coverage_standard_api(request, standard):
    from compliance.services import compute_coverage
    norme = Norme.objects.filter(name__iexact=standard).first() or Norme.objects.filter(name__icontains=standard).first()
    if not norme:
        return Response({'error': f'Standard "{standard}" not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(compute_coverage(norme.id))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_readiness_api(request):
    from compliance.services import compute_audit_readiness
    return Response({'standards': [compute_audit_readiness(n.id) for n in Norme.objects.all()]})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_readiness_standard_api(request, standard):
    from compliance.services import compute_audit_readiness
    norme = Norme.objects.filter(name__iexact=standard).first() or Norme.objects.filter(name__icontains=standard).first()
    if not norme:
        return Response({'error': f'Standard "{standard}" not found.'}, status=status.HTTP_404_NOT_FOUND)
    return Response(compute_audit_readiness(norme.id))


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_maturity_api(request):
    from compliance.services import compute_maturity
    results = [compute_maturity(n.id) for n in Norme.objects.all()]
    overall = round(sum(r['maturity_score'] for r in results) / max(len(results), 1), 1)
    return Response({'overall_maturity': overall, 'standards': results})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def compliance_quality_api(request):
    from compliance.services import compute_all_quality_scores
    from compliance.models import EvidenceQualityScore
    if request.method == 'POST':
        norme_id = request.data.get('norme_id')
        return Response(compute_all_quality_scores(norme_id=int(norme_id) if norme_id else None))
    norme_id = request.query_params.get('norme_id')
    qs = EvidenceQualityScore.objects.all()
    if norme_id:
        qs = qs.filter(evidence__norm_id=int(norme_id))
    agg = qs.aggregate(
        avg_score=Avg('quality_score'),
        excellent=Count('id', filter=Q(quality_level='EXCELLENT')),
        good=Count('id', filter=Q(quality_level='GOOD')),
        warning=Count('id', filter=Q(quality_level='WARNING')),
        poor=Count('id', filter=Q(quality_level='POOR')),
    )
    return Response({
        'total': qs.count(),
        'avg_quality_score': round(float(agg['avg_score'] or 0), 1),
        'distribution': {'EXCELLENT': agg['excellent'] or 0, 'GOOD': agg['good'] or 0,
                         'WARNING': agg['warning'] or 0, 'POOR': agg['poor'] or 0},
    })


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def compliance_risks_api(request):
    from compliance.models import Risk
    from compliance.services import create_audit_log
    if request.method == 'GET':
        qs = Risk.objects.select_related('standard', 'rule').all()
        if request.query_params.get('standard'): qs = qs.filter(standard__name__icontains=request.query_params['standard'])
        if request.query_params.get('status'):   qs = qs.filter(status=request.query_params['status'])
        if request.query_params.get('severity'): qs = qs.filter(severity=request.query_params['severity'])
        items = list(qs.values('id','title','description','severity','likelihood','impact','risk_score',
                               'owner','mitigation_plan','status','due_date','created_at','standard__name','rule__title'))
        return Response({'total': len(items), 'risks': items})
    data = request.data
    try:
        norme = Norme.objects.get(pk=data['standard_id'])
    except (Norme.DoesNotExist, KeyError):
        return Response({'error': 'standard_id required and must be valid.'}, status=status.HTTP_400_BAD_REQUEST)
    rule = None
    if data.get('rule_id'):
        try: rule = Rule.objects.get(pk=data['rule_id'])
        except Rule.DoesNotExist: pass
    risk = Risk.objects.create(
        standard=norme, rule=rule, title=data.get('title',''),
        description=data.get('description',''), likelihood=int(data.get('likelihood',3)),
        impact=int(data.get('impact',3)), owner=data.get('owner',''),
        mitigation_plan=data.get('mitigation_plan',''), status=data.get('status','OPEN'),
        created_by=request.user.username,
    )
    create_audit_log('Risk', risk.id, 'CREATE', request.user.username,
                     new_value={'title': risk.title, 'severity': risk.severity}, request=request)
    return Response({'id': risk.id, 'title': risk.title, 'risk_score': risk.risk_score,
                     'severity': risk.severity}, status=status.HTTP_201_CREATED)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsTeamLeadOrAdmin])
def compliance_risk_update_api(request, risk_id):
    from compliance.models import Risk
    from compliance.services import create_audit_log
    try:
        risk = Risk.objects.get(pk=risk_id)
    except Risk.DoesNotExist:
        return Response({'error': 'Risk not found.'}, status=status.HTTP_404_NOT_FOUND)
    old = {'status': risk.status, 'mitigation_plan': risk.mitigation_plan}
    for field in ['status', 'mitigation_plan', 'owner', 'likelihood', 'impact']:
        if field in request.data:
            setattr(risk, field, request.data[field])
    risk.save()
    create_audit_log('Risk', risk.id, 'UPDATE', request.user.username, old_value=old,
                     new_value={'status': risk.status}, reason=request.data.get('reason',''), request=request)
    return Response({'id': risk.id, 'status': risk.status, 'severity': risk.severity, 'risk_score': risk.risk_score})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_reviews_api(request):
    from compliance.models import PeriodicReview
    from datetime import date
    qs   = PeriodicReview.objects.select_related('rule__norme').all()
    today = date.today()
    ids_overdue, ids_needs, ids_current = [], [], []
    for rev in qs:
        if not rev.next_review_date:          ids_current.append(rev.pk)
        elif rev.next_review_date < today:     ids_overdue.append(rev.pk)
        elif (rev.next_review_date - today).days <= 30: ids_needs.append(rev.pk)
        else:                                  ids_current.append(rev.pk)
    if ids_overdue: PeriodicReview.objects.filter(pk__in=ids_overdue).update(review_status=PeriodicReview.ReviewStatus.OVERDUE)
    if ids_needs:   PeriodicReview.objects.filter(pk__in=ids_needs).update(review_status=PeriodicReview.ReviewStatus.NEEDS_REVIEW)
    if ids_current: PeriodicReview.objects.filter(pk__in=ids_current).update(review_status=PeriodicReview.ReviewStatus.CURRENT)
    qs = PeriodicReview.objects.select_related('rule__norme').all()
    if request.query_params.get('status'):   qs = qs.filter(review_status=request.query_params['status'])
    if request.query_params.get('norme_id'): qs = qs.filter(rule__norme_id=request.query_params['norme_id'])
    items = list(qs.values('id','rule__title','rule__norme__name','review_frequency',
                            'last_review_date','next_review_date','review_status','reviewed_by'))
    return Response({'total': len(items), 'reviews': items})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_critical_controls_api(request):
    from compliance.models import CriticalControl
    from api.models import RuleTrainingSample
    qs = CriticalControl.objects.filter(is_critical=True).select_related('rule__norme')
    if request.query_params.get('norme_id'): qs = qs.filter(rule__norme_id=request.query_params['norme_id'])
    covered_ids = set(RuleTrainingSample.objects.filter(label='approved').values_list('rule_id', flat=True).distinct())
    items = [{'id': cc.id, 'rule_id': cc.rule_id, 'rule_title': cc.rule.title,
              'norme': cc.rule.norme.name, 'control_id': cc.control_id,
              'frameworks': cc.frameworks, 'is_covered': cc.rule_id in covered_ids} for cc in qs]
    covered_count = sum(1 for i in items if i['is_covered'])
    return Response({'total': len(items), 'covered': covered_count,
                     'uncovered': len(items)-covered_count, 'controls': items})


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def compliance_executive_dashboard_api(request):
    from compliance.services import get_executive_dashboard
    return Response(get_executive_dashboard())


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def compliance_refresh_all_api(request):
    from compliance.services import compute_all_quality_scores, compute_coverage, compute_audit_readiness, compute_maturity
    results = {}
    for norme in Norme.objects.all():
        compute_all_quality_scores(norme.id)
        compute_coverage(norme.id)
        compute_audit_readiness(norme.id)
        compute_maturity(norme.id)
        results[norme.name] = 'OK'
    return Response({'refreshed': results})
