SELECT DISTINCT d.*
FROM document d
LEFT JOIN doc_access da
  ON da.doc_id = d.doc_id AND da.department_id = :dept_id
WHERE d.visibility <> 'restricted' OR da.department_id IS NOT NULL
ORDER BY d.updated_at DESC;

SELECT d.doc_id, d.title, dv.version_no, dv.uploaded_at
FROM document d
JOIN document_tag dt ON dt.doc_id = d.doc_id
JOIN tag t ON t.tag_id = dt.tag_id AND t.name = 'Finance'
JOIN document_version dv ON dv.doc_id = d.doc_id AND dv.is_latest = TRUE
ORDER BY dv.uploaded_at DESC
LIMIT 10;

SELECT *
FROM document_version
WHERE doc_id = :doc_id
ORDER BY version_no DESC;

SELECT dep.name AS department, COUNT(*) AS uploads
FROM document_version dv
JOIN app_user u   ON u.user_id = dv.uploaded_by
JOIN department dep ON dep.department_id = u.department_id
WHERE dv.uploaded_at >= NOW() - INTERVAL '30 days'
GROUP BY dep.name
ORDER BY uploads DESC;