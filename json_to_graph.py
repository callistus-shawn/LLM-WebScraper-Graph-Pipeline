def build_graph(tx, articles):
    for row in articles:
        audit_iso = row.get('datetime', "").replace(" ", "T")
        pub_date = row.get('published_date', "")

        tx.run("""
            MERGE (w:WebSource {id: $web_name})
              ON CREATE SET w.description = $web_desc

            CREATE (c:Content {
                title: $title,
                description: $desc,
                published_date: $pub_date,
                audit_insrt: datetime($audit),
                link: $link
            })

            MERGE (w)-[:PUBLISHED]->(c)
        """, {

            "web_name": row.get('web_name', ""),
            "web_desc": row.get('web_desc', ""),
            "title": row.get('headline', ""),
            "desc": row.get('description', ""),
            "pub_date": pub_date,
            "audit": audit_iso,
            "link": row.get('url', "")
        })

        # HAS -> Product
        if row.get('product'):
            tx.run("""
                MERGE (p:Product {name: $product})
                WITH p
                MATCH (c:Content {title: $title})
                MERGE (c)-[:HAS]->(p)
            """, {
                "product": row['product'],
                "title": row['headline']
            })

        # FOR -> Target
        if row.get('product') and row.get('target'):
            tx.run("""
                MERGE (t:Target {name: $target})
                WITH t
                MATCH (p:Product {name: $product})
                MERGE (p)-[:FOR]->(t)
            """, {
                "product": row['product'],
                "target": row['target']
            })
