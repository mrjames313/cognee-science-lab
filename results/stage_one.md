DataPoint findings
------------------

1. Scalar fields become node properties.

2. Nested DataPoint fields:
   - recursively create the target node
   - create a directed edge from parent → child
   - use the Python field name as the relationship name

3. list[DataPoint] creates one edge per list member.

4. Without identity_fields:
   - DataPoint.id defaults to uuid4()
   - repeated logically identical objects become distinct nodes

5. With identity_fields:
   - DataPoint.id is deterministic at object construction time
   - identical identity-field values produce the same UUID
   - aliases are NOT resolved:
       "Helios-1" != "Helios 1"

6. index_fields is independent of identity_fields:
   - identity_fields → graph identity
   - index_fields → fields embedded for semantic retrieval